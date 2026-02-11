package utils

import (
	"log"
	"strings"
	"whatsapp-funnel/llm-go/enums"
	"whatsapp-funnel/llm-go/schemas"
)

var enumAliases = map[string]string{
	"qualifying":    "qualification",
	"qualified":     "qualification",
	"qualify":       "qualification",
	"greet":         "greeting",
	"price":         "pricing",
	"close":         "closed",
	"followups":     "followup",
	"follow_up":     "followup",
	"follow-up":     "followup",
	"ghost":         "ghosted",
	"send":          "send_now",
	"wait":          "wait_schedule",
	"schedule":      "wait_schedule",
	"handoff":       "flag_attention",
	"escalate":      "flag_attention",
	"handoff_human": "flag_attention",
	"very-high":     "very_high",
	"veryhigh":      "very_high",
	"positive":      "curious",
	"negative":      "annoyed",
	"frustrated":    "annoyed",
}

func normalize(v string) string {
	v = strings.TrimSpace(strings.ToLower(v))
	v = strings.ReplaceAll(v, "-", "_")
	v = strings.ReplaceAll(v, " ", "_")
	if alias, ok := enumAliases[v]; ok {
		return alias
	}
	return v
}

func closest(input string, valid []string) string {
	best := ""
	bestScore := -1
	for _, candidate := range valid {
		s := lcs(input, candidate)
		if s > bestScore {
			bestScore = s
			best = candidate
		}
	}
	if bestScore >= 3 {
		return best
	}
	return ""
}

func lcs(a, b string) int {
	m, n := len(a), len(b)
	dp := make([][]int, m+1)
	for i := range dp {
		dp[i] = make([]int, n+1)
	}
	for i := 1; i <= m; i++ {
		for j := 1; j <= n; j++ {
			if a[i-1] == b[j-1] {
				dp[i][j] = dp[i-1][j-1] + 1
			} else if dp[i-1][j] > dp[i][j-1] {
				dp[i][j] = dp[i-1][j]
			} else {
				dp[i][j] = dp[i][j-1]
			}
		}
	}
	return dp[m][n]
}

func NormalizeConversationStage(value string, def enums.ConversationStage) enums.ConversationStage {
	valid := map[string]enums.ConversationStage{
		"greeting": enums.StageGreeting, "qualification": enums.StageQualification,
		"pricing": enums.StagePricing, "cta": enums.StageCTA, "followup": enums.StageFollowup,
		"closed": enums.StageClosed, "lost": enums.StageLost, "ghosted": enums.StageGhosted,
	}
	return normalizeWithFallback(value, valid, def)
}

func NormalizeDecisionAction(value string, def enums.DecisionAction) enums.DecisionAction {
	valid := map[string]enums.DecisionAction{
		"send_now": enums.ActionSendNow, "wait_schedule": enums.ActionWaitSchedule,
		"flag_attention": enums.ActionFlagAttention, "initiate_cta": enums.ActionInitiateCTA,
	}
	return normalizeWithFallback(value, valid, def)
}

func NormalizeIntent(value string, def enums.IntentLevel) enums.IntentLevel {
	valid := map[string]enums.IntentLevel{"low": enums.IntentLow, "medium": enums.IntentMedium, "high": enums.IntentHigh, "very_high": enums.IntentVeryHigh, "unknown": enums.IntentUnknown}
	return normalizeWithFallback(value, valid, def)
}

func NormalizeSentiment(value string, def enums.UserSentiment) enums.UserSentiment {
	valid := map[string]enums.UserSentiment{"neutral": enums.SentimentNeutral, "curious": enums.SentimentCurious, "annoyed": enums.SentimentAnnoyed, "distrustful": enums.SentimentDistrustful, "confused": enums.SentimentConfused, "disappointed": enums.SentimentDisappointed, "uninterested": enums.SentimentUninterested}
	return normalizeWithFallback(value, valid, def)
}

func NormalizeRisk(value string, def enums.RiskLevel) enums.RiskLevel {
	valid := map[string]enums.RiskLevel{"low": enums.RiskLow, "medium": enums.RiskMedium, "high": enums.RiskHigh}
	return normalizeWithFallback(value, valid, def)
}

func normalizeWithFallback[T ~string](value string, valid map[string]T, def T) T {
	if value == "" || value == "null" {
		return def
	}
	n := normalize(value)
	if out, ok := valid[n]; ok {
		return out
	}
	keys := make([]string, 0, len(valid))
	for k := range valid {
		keys = append(keys, k)
	}
	match := closest(n, keys)
	if match != "" {
		log.Printf("enum correction: %s -> %s", value, match)
		return valid[match]
	}
	log.Printf("enum fallback: %s", value)
	return def
}

func FormatCTAs(ctas []schemas.CTA) string {
	if len(ctas) == 0 {
		return "No CTAs defined in dashboard."
	}
	lines := make([]string, 0, len(ctas))
	for _, c := range ctas {
		lines = append(lines, "- ID: "+c.ID+" | Name: "+c.Name)
	}
	return strings.Join(lines, "\n")
}
