package apihelpers

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"time"
	"whatsapp-funnel/llm-go/config"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model          string      `json:"model"`
	Messages       []Message   `json:"messages"`
	Temperature    float64     `json:"temperature"`
	MaxTokens      *int        `json:"max_tokens,omitempty"`
	ResponseFormat interface{} `json:"response_format,omitempty"`
}

type chatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

func ExtractJSONFromText(text string) map[string]interface{} {
	if text == "" {
		return nil
	}
	text = regexp.MustCompile(`^\s+|\s+$`).ReplaceAllString(text, "")
	var direct map[string]interface{}
	if len(text) > 0 && text[0] == '{' && json.Unmarshal([]byte(text), &direct) == nil {
		return direct
	}
	re := regexp.MustCompile(`\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}`)
	if m := re.FindString(text); m != "" {
		var parsed map[string]interface{}
		if json.Unmarshal([]byte(m), &parsed) == nil {
			return parsed
		}
	}
	cb := regexp.MustCompile("```(?:json)?\\s*(\\{.*?\\})\\s*```")
	if m := cb.FindStringSubmatch(text); len(m) > 1 {
		var parsed map[string]interface{}
		if json.Unmarshal([]byte(m[1]), &parsed) == nil {
			return parsed
		}
	}
	return nil
}

func MakeAPICall(cfg config.LLMConfig, messages []Message, responseFormat interface{}, temperature float64, maxTokens *int, stepName string, strict bool) (map[string]interface{}, error) {
	if cfg.BaseURL == "" {
		return nil, errors.New("LLM_BASE_URL missing")
	}
	if cfg.Model == "" {
		return nil, errors.New("LLM_MODEL missing")
	}
	reqBody := ChatRequest{Model: cfg.Model, Messages: messages, Temperature: temperature, MaxTokens: maxTokens, ResponseFormat: responseFormat}
	payload, _ := json.Marshal(reqBody)

	req, err := http.NewRequest(http.MethodPost, cfg.BaseURL+"/chat/completions", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+cfg.APIKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 90 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var out chatResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	if len(out.Choices) == 0 {
		return nil, fmt.Errorf("%s: empty response", stepName)
	}
	content := out.Choices[0].Message.Content

	var parsed map[string]interface{}
	if strict {
		if err := json.Unmarshal([]byte(content), &parsed); err != nil {
			return nil, err
		}
		return parsed, nil
	}
	if err := json.Unmarshal([]byte(content), &parsed); err == nil {
		return parsed, nil
	}
	extracted := ExtractJSONFromText(content)
	if extracted != nil {
		return extracted, nil
	}
	return nil, fmt.Errorf("%s: could not parse JSON", stepName)
}
