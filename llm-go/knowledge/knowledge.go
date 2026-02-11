package knowledge

import (
	"database/sql"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"
)

const (
	EmbeddingModel = "models/gemini-embedding-001"
	EmbeddingDim   = 768
)

type EmbeddingProvider interface {
	EmbedDocument(text string) ([]float64, error)
	EmbedQuery(text string) ([]float64, error)
}

type KnowledgeItem struct {
	ID      string
	Title   string
	Content string
	Score   float64
	Reason  string
}

type Service struct {
	DB       *sql.DB
	Embedder EmbeddingProvider
}

func ProcessVector(vec []float64, targetDim int) []float64 {
	if len(vec) > targetDim {
		vec = vec[:targetDim]
	}
	norm := 0.0
	for _, x := range vec {
		norm += x * x
	}
	norm = math.Sqrt(norm)
	if norm == 0 {
		return vec
	}
	out := make([]float64, len(vec))
	for i, x := range vec {
		out[i] = x / norm
	}
	return out
}

func (s *Service) IngestKnowledge(textContent string, organizationID string, titlePrefix string) (int, error) {
	return s.saveSplits(splitMarkdown(textContent), organizationID, titlePrefix)
}

func (s *Service) IngestPDFText(text string, organizationID string, titlePrefix string) (int, error) {
	return s.saveSplits(recursiveSplit(text, 1000, 200), organizationID, titlePrefix)
}

func (s *Service) saveSplits(splits []string, organizationID string, titlePrefix string) (int, error) {
	if s.DB == nil || s.Embedder == nil {
		return 0, errors.New("db and embedder are required")
	}
	count := 0
	for _, content := range splits {
		v, err := s.Embedder.EmbedDocument(content)
		if err != nil {
			return count, err
		}
		vector := ProcessVector(v, EmbeddingDim)
		title := titlePrefix
		if title == "" {
			title = "General Knowledge"
		}
		_, err = s.DB.Exec(`INSERT INTO knowledge_items (id, organization_id, title, content, embedding, metadata)
			VALUES ($1,$2,$3,$4,$5,$6)`, genID(), organizationID, title, content, floatSliceToPGVector(vector), `{}`)
		if err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}

func (s *Service) SearchKnowledge(query string, organizationID string, topK int, vectorThreshold float64, keywordRankThreshold int) ([]KnowledgeItem, error) {
	if s.DB == nil || s.Embedder == nil {
		return nil, errors.New("db and embedder are required")
	}
	qv, err := s.Embedder.EmbedQuery(query)
	if err != nil {
		return nil, err
	}
	qv = ProcessVector(qv, EmbeddingDim)
	vec := floatSliceToPGVector(qv)
	rows, err := s.DB.Query(`
		WITH vector_results AS (
			SELECT id, title, content, 1 - (embedding <=> $1::vector) AS vec_sim,
				row_number() over (order by embedding <=> $1::vector) as vec_rank
			FROM knowledge_items
			WHERE organization_id = $2
			LIMIT $3
		),
		keyword_results AS (
			SELECT id, title, content,
				row_number() over (order by ts_rank_cd(search_vector, websearch_to_tsquery('english', $4)) DESC) as key_rank
			FROM knowledge_items
			WHERE organization_id = $2
			AND search_vector @@ websearch_to_tsquery('english', $4)
			LIMIT $3
		),
		candidates AS (
			SELECT COALESCE(v.id,k.id) id, COALESCE(v.title,k.title) title, COALESCE(v.content,k.content) content,
				COALESCE(v.vec_rank, NULL) vec_rank, COALESCE(k.key_rank, NULL) key_rank,
				COALESCE(v.vec_sim, 0.0) vec_sim
			FROM vector_results v
			FULL OUTER JOIN keyword_results k ON v.id = k.id
		)
		SELECT id, title, content, vec_sim, vec_rank, key_rank,
			(COALESCE(1.0/(60+vec_rank),0) + COALESCE(1.0/(60+key_rank),0)) as rrf_score
		FROM candidates`, vec, organizationID, topK, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	results := []KnowledgeItem{}
	for rows.Next() {
		var id, title, content string
		var vecSim, rrf float64
		var vecRank, keyRank sql.NullInt64
		if err := rows.Scan(&id, &title, &content, &vecSim, &vecRank, &keyRank, &rrf); err != nil {
			return nil, err
		}
		strongSemantic := vecSim > vectorThreshold
		strongKeyword := keyRank.Valid && int(keyRank.Int64) <= keywordRankThreshold
		if strongSemantic || strongKeyword {
			reason := "keyword"
			if strongSemantic {
				reason = "semantic"
			}
			results = append(results, KnowledgeItem{ID: id, Title: title, Content: content, Score: rrf, Reason: reason})
		}
	}
	return results, nil
}

func splitMarkdown(text string) []string {
	parts := strings.Split(text, "\n\n")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func recursiveSplit(text string, size, overlap int) []string {
	if len(text) <= size {
		return []string{text}
	}
	chunks := []string{}
	for start := 0; start < len(text); start += size - overlap {
		end := start + size
		if end > len(text) {
			end = len(text)
		}
		chunks = append(chunks, text[start:end])
		if end == len(text) {
			break
		}
	}
	return chunks
}

func floatSliceToPGVector(v []float64) string {
	parts := make([]string, len(v))
	for i, f := range v {
		parts[i] = fmt.Sprintf("%f", f)
	}
	return "[" + strings.Join(parts, ",") + "]"
}

func genID() string { return fmt.Sprintf("gen-%d", time.Now().UnixNano()) }
