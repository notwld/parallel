# Parallel product brief

Parallel is a persistent social world where real people inhabit the same fictional universe. Their decisions change its history. Players discover information, talk to people, decide who to trust, act, experience consequences, and encounter new problems. The AI makes consequences legible and plausible; the database and authored rules decide what becomes real.

## Flagship scenario from the user

The flagship world is **Earth-2097**. A mysterious city appears in the Atlantic Ocean. Journalists, scientists, officials, business owners, spies, and citizens receive different accounts of what it contains. The user described aircraft sightings, secret research, public leaks, institutional reactions, protests, and escalating international tension as examples of how people can cause the next event.

These are scenario possibilities, not a prewritten sequence the AI must force. The discovery that humans live inside the city is an example of a canonical secret held by very few characters. Keep seed secrets in backend fixtures only, never in browser fixtures or public briefings. The original document's Earth-1842/Antarctic examples demonstrate mechanics; they do not override the user's Earth-2097 setting.

## Four sources of new problems

1. Authored or AI-proposed world events start situations within configured rules.
2. User actions cause immediate and delayed consequences.
3. Hidden information is discovered, verified, distorted, or leaked.
4. Conflicts between people and organizations create further decisions.

Preserve the causal chain so players can explain what changed and why. An official cannot simply cause a war by writing a post; capabilities, institutions, preconditions, and review rules determine which effects are possible.

## First milestones

**Technical prototype:** two characters with different knowledge; one secret, a claim, evidence, a share with provenance, a typed action, and a durable consequence. A briefing for the less-informed character cannot reveal the canonical secret. This follows specification section 20.3.

**Closed alpha:** 50–500 people in one curated world, with onboarding, roles, feed, articles, Intel, DMs, organizations, locations, notifications, timeline, daily briefings, and moderator controls. Thousands of simultaneous participants are a later load target, not a claim about this starter.

**Success:** people return to learn what their actions caused, need other humans' knowledge, and can trace consequences without frequent leaks or contradictions. Establish numeric product targets from alpha observations rather than inventing retention figures.

## Scope boundaries

The initialized repository is a development foundation. It does not yet contain gameplay, login endpoints, the Earth-2097 seed world, knowledge models, or a running AI simulation.

Defer markets, currencies, structured elections, creator marketplaces, world forks, native clients, 3D navigation, and autonomous NPC populations. A business owner's initial actions can use ordinary organization capabilities; buying stocks requires the deferred ledger/market system.

All worlds must enforce platform safety rules while distinguishing fictional conflict from real-world abuse. DMs are not end-to-end encrypted in the proposed server architecture; never describe them as such.
