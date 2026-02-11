package config

import (
	"os"
	"path/filepath"
	"strings"
)

// LLMConfig mirrors the original Python llm.config.LLMConfig.
type LLMConfig struct {
	APIKey       string
	Model        string
	BaseURL      string
	GoogleAPIKey string
}

// LoadConfig reads .env.dev (if present) and then environment variables.
func LoadConfig() LLMConfig {
	loadDotEnvDev()
	return LLMConfig{
		APIKey:       os.Getenv("GROQ_API_KEY"),
		Model:        os.Getenv("LLM_MODEL"),
		BaseURL:      os.Getenv("LLM_BASE_URL"),
		GoogleAPIKey: os.Getenv("GOOGLE_API_KEY"),
	}
}

func loadDotEnvDev() {
	cwd, err := os.Getwd()
	if err != nil {
		return
	}
	path := filepath.Join(cwd, ".env.dev")
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.Trim(strings.TrimSpace(parts[1]), `"`)
		_ = os.Setenv(key, value)
	}
}
