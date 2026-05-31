# Autonomous Task Expansion — Revenue-Focused Tasks

Add three new autonomous tasks to address Priestley audit gaps: Publish, Profile, and Partnerships. These tasks systematically clear obstacles on revenue paths (VoidDrift Play Store, YouTube monetization, OpenAgent consulting leads).

## New Tasks to Add

### blog_structure_generator (Sunday 1AM)
- **Schedule:** cron, Sunday 1AM
- **Purpose:** Generate blog post skeleton using RFD Content Frame (MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT)
- **Data sources:** get_recent_commits, YouTube performance, itch.io stats
- **Output:** Save to memory as 'Blog draft YYYY-MM-DD'
- **Leverage:** Addresses Publish gap (4 stale posts blocking consulting credibility)

### community_opportunity_scout (Every 3h, 7AM–11PM)
- **Schedule:** interval, 180 minutes
- **Purpose:** Monitor r/incremental_games, r/bevy, r/rust, r/gamedev for threads where expertise adds value
- **Action:** Draft potential responses, save to memory, flag for review
- **Leverage:** Authentic comments drive subscribers more than posting; algorithm feeds on engagement

### consulting_lead_scout (Daily 7AM)
- **Schedule:** cron, 7AM daily
- **Purpose:** Search for Python, Rust, data automation, Selenium contract work
- **Exclusions:** Convoso/dialer software (Non-Compete boundary)
- **Action:** Create personal tasks for qualified leads
- **Leverage:** Brownbook ETL example → people need that skill and will pay

## Tasks NOT to Automate

- Actual blog post prose (requires authentic voice)
- Social media posting (requires human judgment)
- Client outreach (requires human decision)

The agent drafts and flags. User decides, edits, and executes.

## Implementation Order

1. **blog_structure_generator** — highest leverage for current state
2. **community_opportunity_scout** — audience growth
3. **consulting_lead_scout** — consulting leads

## Current State

- 4 autonomous tasks running overnight (email_triage, nightly_snapshot, itch_reddit_check, openagent_momentum_tracker)
- Tomorrow's 7AM briefing will show first overnight actions
- Review results before adding new tasks

## Next Session

1. Review overnight autonomous actions in 7AM briefing
2. Implement blog_structure_generator
3. Test with manual invocation
4. Add to TASKS dict
5. Commit and deploy
