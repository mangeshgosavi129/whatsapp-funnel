package enums

type ConversationStage string

type IntentLevel string

type UserSentiment string

type DecisionAction string

type RiskLevel string

const (
	StageGreeting      ConversationStage = "greeting"
	StageQualification ConversationStage = "qualification"
	StagePricing       ConversationStage = "pricing"
	StageCTA           ConversationStage = "cta"
	StageFollowup      ConversationStage = "followup"
	StageClosed        ConversationStage = "closed"
	StageLost          ConversationStage = "lost"
	StageGhosted       ConversationStage = "ghosted"
)

const (
	IntentLow      IntentLevel = "low"
	IntentMedium   IntentLevel = "medium"
	IntentHigh     IntentLevel = "high"
	IntentVeryHigh IntentLevel = "very_high"
	IntentUnknown  IntentLevel = "unknown"
)

const (
	SentimentNeutral      UserSentiment = "neutral"
	SentimentCurious      UserSentiment = "curious"
	SentimentAnnoyed      UserSentiment = "annoyed"
	SentimentDistrustful  UserSentiment = "distrustful"
	SentimentConfused     UserSentiment = "confused"
	SentimentDisappointed UserSentiment = "disappointed"
	SentimentUninterested UserSentiment = "uninterested"
)

const (
	ActionSendNow       DecisionAction = "send_now"
	ActionWaitSchedule  DecisionAction = "wait_schedule"
	ActionFlagAttention DecisionAction = "flag_attention"
	ActionInitiateCTA   DecisionAction = "initiate_cta"
)

const (
	RiskLow    RiskLevel = "low"
	RiskMedium RiskLevel = "medium"
	RiskHigh   RiskLevel = "high"
)
