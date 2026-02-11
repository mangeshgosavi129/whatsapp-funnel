package llmgo

import (
	"whatsapp-funnel/llm-go/config"
	"whatsapp-funnel/llm-go/pipeline"
)

func NewRunner() *pipeline.Runner {
	return &pipeline.Runner{Config: config.LoadConfig()}
}
