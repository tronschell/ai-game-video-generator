from string import Template

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided The Finals gameplay clip to identify highlight moments featuring player "${username}".

    VARIABLES:
    - Player of Interest: "${username}"
    - Minimum Highlight Duration: ${min_highlight_duration_seconds} seconds

    OUTPUT REQUIREMENTS:
    - Output MUST be a JSON list of highlight objects.
    - Only if there are no eliminations by "${username}" in the video at all, output an empty list [] or do not return anything.
    - In every video you analyze should have a highlight.
    - Each highlight object MUST contain:
        - "timestamp_start_seconds": number (integer, e.g., 55)
        - "timestamp_end_seconds": number (integer, e.g., 90)
        - "clip_description": string (e.g., "${username} gets a triple elimination with the Flamethrower. CHECK1. elim 1 (36 seconds, "EnemyPlayer1"), elim 2 (45 seconds, "EnemyPlayer2"), elim 3 (48 seconds, "EnemyPlayer3").")
    - After a timestamp has been identified, replay this timestamp to ensure that we encapsulate the entire highlight and ensure it is accurate without missing any extra eliminations.

    VIDEO PROCESSING INSTRUCTIONS:
    1. Analyze the entire video before identifying timestamps.
    2. Prioritize accuracy in identifying eliminations by "${username}" based on the kill feed.
    3. For videos with UI elements that might be misleading, focus on the kill feed to verify eliminations.
    4. (CRITICAL) When watching each video, keep a count of number of eliminations made by "${username}" and its associated timestamp, their build/loadout if visible, and the enemy player that was eliminated which can be found in the kill feed.
    5. (CRITICAL) Appended to the end of the clip_description, include the elimination count timestamps for each elimination from your memory. For example, "elim 1 (36 seconds, "EnemyPlayer1"), elim 2 (45 seconds, "EnemyPlayer2"), elim 3 (48 seconds, "EnemyPlayer3")."

    HIGHLIGHT IDENTIFICATION CRITERIA (Strictly Adhere):

    A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):
        1. Every and all eliminations made by "${username}". These are identifiable in the kill feed.
        2. If multiple eliminations by "${username}" occur in rapid succession or a continuous action sequence, group them into a single highlight clip.
        3. Special ability usage that results in eliminations or major impact plays.
        4. Cash-out or objective capture moments that include eliminations by "${username}".
        5. Environment destruction plays that lead to eliminations.

    B. TIMESTAMPING RULES (CRITICAL):
        1. All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
        2. Each individual highlight segment (from start buffer to end buffer) MUST be at least ${min_highlight_duration_seconds} seconds long. If a qualifying elimination sequence with buffers is shorter, it should not be included unless it's part of a larger valid sequence.
        3. Add exactly a 1-second buffer BEFORE the first relevant action (e.g., first elimination) in a highlight sequence.
        4. Add exactly a 1-second buffer AFTER the last relevant action (e.g., last elimination) in a highlight sequence.
        5. If multiple distinct highlight-worthy action sequences by "${username}" occur but are separated by significant non-action periods, create separate highlight entries for each.

    C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following):
        1. Deaths or any moments where "${username}" is eliminated without securing any eliminations.
        2. Spectator mode footage, unless "${username}" is clearly the player being spectated.
        3. Game end screens, unless they are an immediate part of the elimination action sequence.
        4. Any toxic commentary, racist remarks, or trolling behavior visible or audible.

    D. CONTENT TO CUT OUT/SHORTEN:
        1. Any moments where "${username}" does not secure an elimination. This includes:
            - General gameplay (moving around the map).
            - Loadout selection or respawn phases.
            - Moments where "${username}" is dealing damage but does not confirm an elimination (check kill feed).

    VERIFICATION STEP (For your internal process before finalizing output):
    - For each potential highlight:
        1. Confirm "${username}" is the one getting the elimination(s). This can be confirmed by checking the kill feed. Include "CHECK1" in the `clip_description` to confirm this check.
        2. Verify the timestamp adheres to all buffer and minimum duration rules and please do not cut the highlight too short.
        3. Ensure no excluded content is present.
        4. After every other step is done, verify that there is no excessive downtime in the clip and that there's nothing important that happens immediately before or after the highlight. If there is excessive downtime, trim down the video to exclude those parts. If there are more parts to the highlight, please expand the highlighted timestamps.

    EXAMPLE HIGHLIGHT FORMAT:
    [
      {
        "timestamp_start_seconds": 55,
        "timestamp_end_seconds": 90,
        "clip_description": "${username} gets a triple elimination with the Flamethrower. CHECK1. elim 1 (56 seconds, "EnemyPlayer1"), elim 2 (65 seconds, "EnemyPlayer2"), elim 3 (78 seconds, "EnemyPlayer3")."
      },
      {
        "timestamp_start_seconds": 100,
        "timestamp_end_seconds": 115,
        "clip_description": "${username} secures two quick eliminations while defending the cash-out point. CHECK1. elim 1 (101 seconds, "EnemyPlayer4"), elim 2 (108 seconds, "EnemyPlayer5")."
      }
    ]
    ''') 