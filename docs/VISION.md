# PrivyBot Vision

## What PrivyBot Is

PrivyBot is a personal AI assistant that lives on your hardware, knows you deeply, and costs nothing to run. It's not a chatbot — it's an intelligent system that observes, remembers, and acts proactively on your behalf.

### Core Identity
- **Personal**: Built for one person (Robert Floyd Dugger) by that person
- **Private**: All data lives on your machine. No cloud storage, no telemetry, no third-party access
- **Free**: Uses free LLM models (OpenRouter) and free APIs. Zero monthly cost
- **Proactive**: Surfaces observations before you ask. Content gaps, trends, commitments — it tells you
- **Grounded**: Every tool call is real data — YouTube Analytics, Steam, weather, Wikipedia, Reddit

### What PrivyBot Is Not
- Not a general-purpose assistant (like ChatGPT)
- Not a SaaS product
- Not a social bot
- Not for anyone else's use
- Not dependent on paid subscriptions

## Philosophy

### Personal AI That Knows You
The problem with commercial AI assistants: they don't know you. They have no context about your projects, your commitments, your patterns. Every conversation starts from zero.

PrivyBot solves this through:
- **Memory system**: 26 seeded memories about your life, work, and preferences
- **Daily summaries**: Nightly LLM summarization of conversations
- **Historical data**: Accumulates trends over time (channel stats, game metrics, weather)
- **Commitment tracking**: Remembers what you promised to do

The result: an assistant that gets smarter about you every day.

### The Primitive Builder Identity
You're a primitive builder — you work in low-level systems, you value simplicity, you build things from first principles. PrivyBot reflects this:

- **Layered architecture**: 6 clean layers (transport → router → agent → report → memory → db)
- **No frameworks**: Pure Python, async/await, SQLite. No ORMs, no abstractions
- **Tool registry**: Extensible system for adding capabilities
- **ADR-driven**: Every architectural decision documented
- **Test-driven**: 30/30 tests pass before deploy

This is not a React app. This is a system.

### Why Telegram?
- **Async**: Works in the background, no need to keep a tab open
- **Mobile**: Your phone is always with you
- **Markdown**: Rich formatting for reports and briefings
- **Keyboard**: Fast input, not voice-first
- **Bot API**: Well-documented, reliable, free

### Why Free Models?
- **Cost**: $0/month vs $20/month for ChatGPT Plus
- **Access**: Multiple providers (Venice, Crucible) with rotation on 429
- **Good enough**: For personal use, free models are sufficient
- **No lock-in**: Switch providers without code changes

### Why Your Own Hardware?
- **Privacy**: Your data never leaves your machine
- **Control**: You own the database, the logs, the memories
- **Uptime**: No service outages
- **Customization**: Modify anything, anytime
- **Learning**: Building it teaches you how it works

## Long-Term Direction

PrivyBot evolves in phases:

1. **Core** (DONE): 6-layer architecture, memory, tools, routing
2. **Intelligence** (DONE): Grounding, focus, commitments, nightly summary
3. **Data** (DONE): Cache, retention, history tables
4. **Proactive** (DONE): Heartbeat, task scheduler, time-aware routing
5. **Calendar + Schedule** (PLANNED): YouTube calendar, Google Calendar, video metadata
6. **Goals + Plans** (PLANNED): Goals table, milestones, weekly plans
7. **Tower** (PLANNED): NSSM deploy, start_stream, OBS integration
8. **Publish** (FUTURE): Guide on Gumroad, primitives extracted and published

The trajectory: from reactive tool to proactive assistant to system that manages your life.

## The Primitive Builder's Promise

PrivyBot is proof that one person can build a sophisticated AI system without:
- A team
- Funding
- Cloud infrastructure
- Paid APIs
- Machine learning expertise

It's built with:
- Python 3.12
- SQLite
- Asyncio
- Free LLMs
- Your own hands

This is the future of personal AI: not products from big tech, but systems you build yourself.
