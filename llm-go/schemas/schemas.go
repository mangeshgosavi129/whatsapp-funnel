package schemas

import (
	"whatsapp-funnel/llm-go/enums"
)

type MessageContext struct {
	Sender    string `json:"sender"`
	Text      string `json:"text"`
	Timestamp string `json:"timestamp"`
}

type TimingContext struct {
	NowLocal           string  `json:"now_local"`
	LastUserMessageAt  *string `json:"last_user_message_at,omitempty"`
	LastBotMessageAt   *string `json:"last_bot_message_at,omitempty"`
	WhatsAppWindowOpen bool    `json:"whatsapp_window_open"`
}

type NudgeContext struct {
	FollowupCount24h int `json:"followup_count_24h"`
	TotalNudges      int `json:"total_nudges"`
}

type CTA struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type PipelineInput struct {
	OrganizationID          string                  `json:"organization_id"`
	BusinessName            string                  `json:"business_name"`
	BusinessDescription     string                  `json:"business_description"`
	FlowPrompt              string                  `json:"flow_prompt"`
	AvailableCTAs           []CTA                   `json:"available_ctas"`
	RollingSummary          string                  `json:"rolling_summary"`
	LastMessages            []MessageContext        `json:"last_messages"`
	ConversationStage       enums.ConversationStage `json:"conversation_stage"`
	ConversationMode        string                  `json:"conversation_mode"`
	IntentLevel             enums.IntentLevel       `json:"intent_level"`
	UserSentiment           enums.UserSentiment     `json:"user_sentiment"`
	ActiveCTAID             *string                 `json:"active_cta_id,omitempty"`
	Timing                  TimingContext           `json:"timing"`
	Nudges                  NudgeContext            `json:"nudges"`
	MaxWords                int                     `json:"max_words"`
	QuestionsPerMessage     int                     `json:"questions_per_message"`
	LanguagePref            string                  `json:"language_pref"`
	DynamicKnowledgeContext *string                 `json:"dynamic_knowledge_context,omitempty"`
}

type RiskFlags struct {
	SpamRisk          enums.RiskLevel `json:"spam_risk"`
	PolicyRisk        enums.RiskLevel `json:"policy_risk"`
	HallucinationRisk enums.RiskLevel `json:"hallucination_risk"`
}

type GenerateOutput struct {
	ThoughtProcess      string                  `json:"thought_process"`
	IntentLevel         enums.IntentLevel       `json:"intent_level"`
	UserSentiment       enums.UserSentiment     `json:"user_sentiment"`
	RiskFlags           RiskFlags               `json:"risk_flags"`
	Action              enums.DecisionAction    `json:"action"`
	NewStage            enums.ConversationStage `json:"new_stage"`
	ShouldRespond       bool                    `json:"should_respond"`
	SelectedCTAID       *string                 `json:"selected_cta_id"`
	CTAScheduledAt      *string                 `json:"cta_scheduled_at"`
	FollowupInMinutes   int                     `json:"followup_in_minutes"`
	FollowupReason      string                  `json:"followup_reason"`
	MessageText         string                  `json:"message_text"`
	MessageLanguage     string                  `json:"message_language"`
	Confidence          float64                 `json:"confidence"`
	NeedsHumanAttention bool                    `json:"needs_human_attention"`
}

type MemoryOutput struct {
	UpdatedRollingSummary string `json:"updated_rolling_summary"`
	NeedsRecursiveSummary bool   `json:"needs_recursive_summary"`
}

type PipelineResult struct {
	Generate               GenerateOutput `json:"generate"`
	Memory                 *MemoryOutput  `json:"memory,omitempty"`
	PipelineLatencyMs      int            `json:"pipeline_latency_ms"`
	TotalTokensUsed        int            `json:"total_tokens_used"`
	NeedsBackgroundSummary bool           `json:"needs_background_summary"`
}

func (p PipelineResult) ShouldSendMessage() bool {
	return p.Generate.ShouldRespond && p.Generate.MessageText != ""
}

func (p PipelineResult) ShouldScheduleFollowup() bool {
	return p.Generate.Action == enums.ActionWaitSchedule
}

func (p PipelineResult) ShouldEscalate() bool {
	return p.Generate.NeedsHumanAttention
}

func (p PipelineResult) ShouldInitiateCTA() bool {
	return p.Generate.Action == enums.ActionInitiateCTA
}
