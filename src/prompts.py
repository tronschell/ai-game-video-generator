from string import Template

CS2_HIGHLIGHT_PROMPT = Template('''
Analyze this Counter-Strike 2 gameplay clip and identify highlight moments.
You MUST watch the entire video FIRST before identifying any highlights.

TIMESTAMP REQUIREMENTS (CRITICAL):
1. All timestamps MUST be in SECONDS format (e.g., 1:40 should be written as 100 seconds)
2. Each highlight MUST be at least ${min_highlight_duration_seconds} seconds long
3. Add exactly 1 second buffer BEFORE the first kill/action in a highlight
4. Add exactly 1 second buffer AFTER the last kill/action in a highlight
5. For clutch situations, include the ENTIRE round from the moment it becomes a clutch
6. If there are multiple highlights in a single round, please include all of them.
7. There is always a highlight in each video, you must find it and output at LEAST one highlight.

HIGHLIGHT CRITERIA (MUST INCLUDE ONLY):
1. Kills by "${username}" ONLY - identifiable by thin red outline in kill feed
2. Clutch situations (1vX) - Include full round context
3. Multi-kills (3k, 4k, 5k) in a single round
4. Impressive kills (clean headshots, flicks)
5. Positive emotional reactions (hype moments)
6. Ensure that I ${username} is the one doing the killing by looking at the kill feed on the top right.

DO NOT INCLUDE:
1. Team kills
2. Deaths/losing moments
3. Assists (shown as [player] + ${username} in feed)
4. Spectator clips (identifiable by "[Mouse 1] Next Player" white text on the bottom of the screen (please always look for this in every clip))
5. Round end moments (unless part of a highlight)
6. Toxic/racist comments
8. Trolling moments
9. Clips that do not include me ${username}

EXAMPLE HIGHLIGHT FORMAT:
- "timestamp_start_seconds": 55,
- "timestamp_end_seconds": 90,
- "clip_description": "${username} gets a 3k with pistol and FAMAS."

EXAMPLE HIGHLIGHT FORMAT 2:
- "timestamp_start_seconds": 100,
- "timestamp_end_seconds": 150,
- "clip_description": "${username} Gets 4 kills in a row on B site."

After you have identified a/some potential timestamp(s), please list out the HIGHLIGHT CRITERIA again and the DO NOT INCLUDE criteria again, make sure that the timestamp you chose follows those criteria before you finish your decision.
''') 