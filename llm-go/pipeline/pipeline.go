package pipeline

import (
	"log"
	"strconv"
	"strings"
	"time"
	"whatsapp-funnel/llm-go/config"
	"whatsapp-funnel/llm-go/enums"
	"whatsapp-funnel/llm-go/knowledge"
	"whatsapp-funnel/llm-go/schemas"
	gen "whatsapp-funnel/llm-go/steps/generate"
)

type Runner struct {
	Config    config.LLMConfig
	Knowledge *knowledge.Service
}

func (r *Runner) RunPipeline(context schemas.PipelineInput, userMessage string) schemas.PipelineResult {
	start := time.Now()
	if r.Knowledge != nil {
		results, err := r.Knowledge.SearchKnowledge(userMessage, context.OrganizationID, 5, 0.65, 5)
		if err != nil {
			msg := "Error retrieving knowledge."
			context.DynamicKnowledgeContext = &msg
			log.Printf("RAG failed: %v", err)
		} else if len(results) == 0 {
			msg := "No relevant knowledge found."
			context.DynamicKnowledgeContext = &msg
		} else {
			chunks := make([]string, 0, len(results))
			for _, item := range results {
				chunks = append(chunks, "Source: "+item.Title+" (Confidence: "+formatScore(item.Score)+")\nContent: "+item.Content)
			}
			msg := strings.Join(chunks, "\n\n")
			context.DynamicKnowledgeContext = &msg
		}
	}

	generateOutput, _, tokens := gen.RunGenerate(r.Config, context)
	return schemas.PipelineResult{
		Generate:               generateOutput,
		PipelineLatencyMs:      int(time.Since(start).Milliseconds()),
		TotalTokensUsed:        tokens,
		NeedsBackgroundSummary: true,
	}
}

func (r *Runner) RunFollowupPipeline(context schemas.PipelineInput) schemas.PipelineResult {
	return r.RunPipeline(context, "[System: Scheduled follow-up triggered]")
}

func EmergencyResult(context schemas.PipelineInput) schemas.PipelineResult {
	return schemas.PipelineResult{Generate: schemas.GenerateOutput{
		ThoughtProcess:      "Critical System Failure",
		IntentLevel:         enums.IntentUnknown,
		UserSentiment:       enums.SentimentNeutral,
		RiskFlags:           schemas.RiskFlags{SpamRisk: enums.RiskLow, PolicyRisk: enums.RiskLow, HallucinationRisk: enums.RiskLow},
		Action:              enums.ActionWaitSchedule,
		NewStage:            context.ConversationStage,
		ShouldRespond:       false,
		Confidence:          0.0,
		NeedsHumanAttention: true,
		MessageText:         "",
	}, NeedsBackgroundSummary: false}
}

func formatScore(v float64) string { return strconv.FormatFloat(v, 'f', 2, 64) }
