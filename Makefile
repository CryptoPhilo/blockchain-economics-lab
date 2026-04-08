.PHONY: dev build test lint format clean deploy db-migrate

# Development
dev:
	npm run dev

build:
	npm run build

test:
	npm test

lint:
	npm run lint

format:
	npx prettier --write "src/**/*.{ts,tsx,json}"

clean:
	rm -rf .next node_modules

# Database
db-migrate:
	npx supabase db push

db-reset:
	npx supabase db reset

db-types:
	npx supabase gen types typescript --project-id wbqponoiyoeqlepxogcb > src/lib/database.types.ts

# Deployment
deploy-preview:
	npx vercel

deploy-prod:
	npx vercel --prod

# Agent Operations
heartbeat:
	node scripts/agent-heartbeat.js --agents=all

publish-report:
	@read -p "Report slug: " slug; node scripts/publish-report.js --slug=$$slug

# Setup
setup:
	npm install
	npx husky install
	cp .env.example .env.local
	@echo "✅ Setup complete. Edit .env.local with your keys."
