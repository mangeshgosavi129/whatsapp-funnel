package memory

import (
	"fmt"
	"time"
	"whatsapp-funnel/llm-go/apihelpers"
	"whatsapp-funnel/llm-go/config"
	"whatsapp-funnel/llm-go/prompts"
	"whatsapp-funnel/llm-go/schemas"
)

var memorySchema = map[string]interface{}{
	"name":   "memory_output",
	"strict": false,
	"schema": map[string]interface{}{
		"type": "object",
		"properties": map[string]interface{}{
			"updated_rolling_summary": map[string]string{"type": "string"},
			"needs_recursive_summary": map[string]string{"type": "boolean"},
		},
	},
}

func RunMemory(cfg config.LLMConfig, context schemas.PipelineInput, userMessage string, generateOutput schemas.GenerateOutput) string {
	output, _, err := runMemoryLLM(cfg, context, userMessage, generateOutput)
	if err != nil {
		if context.RollingSummary != "" {
			return context.RollingSummary
		}
		return "No summary available"
	}
	return output.UpdatedRollingSummary
}

func runMemoryLLM(cfg config.LLMConfig, context schemas.PipelineInput, userMessage string, generateOutput schemas.GenerateOutput) (schemas.MemoryOutput, int, error) {
	botMessage := generateOutput.MessageText
	if botMessage == "" {
		botMessage = "(No response sent)"
	}
	actionTaken := fmt.Sprintf("Action: %s, Stage: %s", generateOutput.Action, generateOutput.NewStage)
	summary := context.RollingSummary
	if summary == "" {
		summary = "No prior summary"
	}
	prompt := fmt.Sprintf(prompts.MemoryUserTemplate, summary, userMessage, botMessage, actionTaken)
	start := time.Now()
	data, err := apihelpers.MakeAPICall(cfg,
		[]apihelpers.Message{{Role: "system", Content: prompts.MemorySystemPrompt}, {Role: "user", Content: prompt}},
		map[string]interface{}{"type": "json_schema", "json_schema": memorySchema},
		0.7, intPtr(2000), "Memory", false,
	)
	if err != nil {
		return schemas.MemoryOutput{}, int(time.Since(start).Milliseconds()), err
	}
	out := schemas.MemoryOutput{}
	if v, ok := data["updated_rolling_summary"].(string); ok {
		out.UpdatedRollingSummary = v
	}
	if v, ok := data["needs_recursive_summary"].(bool); ok {
		out.NeedsRecursiveSummary = v
	}
	return out, int(time.Since(start).Milliseconds()), nil
}

func intPtr(v int) *int { return &v }
