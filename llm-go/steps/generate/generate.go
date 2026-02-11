package generate

import (
	"fmt"
	"strings"
	"time"
	"whatsapp-funnel/llm-go/apihelpers"
	"whatsapp-funnel/llm-go/config"
	"whatsapp-funnel/llm-go/enums"
	"whatsapp-funnel/llm-go/prompts"
	"whatsapp-funnel/llm-go/schemas"
	"whatsapp-funnel/llm-go/utils"
)

var generateSchema = map[string]interface{}{
	"name":   "generate_output",
	"strict": true,
	"schema": map[string]interface{}{"type": "object"},
}

func formatMessages(messages []schemas.MessageContext) string {
	if len(messages) == 0 {
		return "No messages yet"
	}
	lines := make([]string, 0, len(messages))
	for _, msg := range messages {
		lines = append(lines, fmt.Sprintf("[%s] %s", msg.Sender, msg.Text))
	}
	return strings.Join(lines, "\n")
}

func buildUserPrompt(context schemas.PipelineInput) string {
	knowledge := "No specific knowledge retrieved."
	if context.DynamicKnowledgeContext != nil {
		knowledge = *context.DynamicKnowledgeContext
	}
	summary := context.RollingSummary
	if summary == "" {
		summary = "No summary yet"
	}
	return fmt.Sprintf(prompts.GenerateUserTemplate,
		context.BusinessName,
		context.BusinessDescription,
		context.FlowPrompt,
		knowledge,
		summary,
		context.ConversationStage,
		context.Nudges.TotalNudges,
		context.Timing.NowLocal,
		context.Timing.WhatsAppWindowOpen,
		utils.FormatCTAs(context.AvailableCTAs),
		formatMessages(context.LastMessages),
	)
}

func validateAndBuildOutput(data map[string]interface{}, context schemas.PipelineInput) schemas.GenerateOutput {
	rf := map[string]interface{}{}
	if v, ok := data["risk_flags"].(map[string]interface{}); ok {
		rf = v
	}
	get := func(m map[string]interface{}, key string) string {
		if v, ok := m[key].(string); ok {
			return v
		}
		return ""
	}
	output := schemas.GenerateOutput{
		ThoughtProcess:      get(data, "thought_process"),
		IntentLevel:         utils.NormalizeIntent(get(data, "intent_level"), enums.IntentUnknown),
		UserSentiment:       utils.NormalizeSentiment(get(data, "user_sentiment"), enums.SentimentNeutral),
		Action:              utils.NormalizeDecisionAction(get(data, "action"), enums.ActionWaitSchedule),
		NewStage:            utils.NormalizeConversationStage(get(data, "new_stage"), context.ConversationStage),
		ShouldRespond:       boolValue(data["should_respond"]),
		FollowupInMinutes:   intValue(data["followup_in_minutes"]),
		FollowupReason:      get(data, "followup_reason"),
		MessageText:         get(data, "message_text"),
		MessageLanguage:     get(data, "message_language"),
		Confidence:          floatValue(data["confidence"], 0.5),
		NeedsHumanAttention: boolValue(data["needs_human_attention"]),
		RiskFlags: schemas.RiskFlags{
			SpamRisk:          utils.NormalizeRisk(get(rf, "spam_risk"), enums.RiskLow),
			PolicyRisk:        utils.NormalizeRisk(get(rf, "policy_risk"), enums.RiskLow),
			HallucinationRisk: utils.NormalizeRisk(get(rf, "hallucination_risk"), enums.RiskLow),
		},
	}
	if s, ok := data["selected_cta_id"].(string); ok {
		output.SelectedCTAID = &s
	}
	if s, ok := data["cta_scheduled_at"].(string); ok {
		output.CTAScheduledAt = &s
	}
	if output.MessageLanguage == "" {
		output.MessageLanguage = "en"
	}
	return output
}

func boolValue(v interface{}) bool { b, _ := v.(bool); return b }
func intValue(v interface{}) int {
	if f, ok := v.(float64); ok {
		return int(f)
	}
	return 0
}
func floatValue(v interface{}, def float64) float64 {
	if f, ok := v.(float64); ok {
		return f
	}
	return def
}

func get(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func RunGenerate(cfg config.LLMConfig, context schemas.PipelineInput) (schemas.GenerateOutput, int, int) {
	prompt := buildUserPrompt(context)
	start := time.Now()
	data, err := apihelpers.MakeAPICall(cfg,
		[]apihelpers.Message{{Role: "system", Content: prompts.GenerateSystemPrompt}, {Role: "user", Content: prompt}},
		map[string]interface{}{"type": "json_schema", "json_schema": generateSchema},
		0.3, nil, "Generate", true,
	)
	if err != nil {
		return schemas.GenerateOutput{
			ThoughtProcess:      "System Error - Fallback triggered",
			IntentLevel:         context.IntentLevel,
			UserSentiment:       context.UserSentiment,
			RiskFlags:           schemas.RiskFlags{SpamRisk: enums.RiskLow, PolicyRisk: enums.RiskLow, HallucinationRisk: enums.RiskLow},
			Action:              enums.ActionWaitSchedule,
			NewStage:            context.ConversationStage,
			ShouldRespond:       false,
			Confidence:          0,
			NeedsHumanAttention: true,
			MessageText:         "",
		}, int(time.Since(start).Milliseconds()), 0
	}
	return validateAndBuildOutput(data, context), int(time.Since(start).Milliseconds()), 0
}
