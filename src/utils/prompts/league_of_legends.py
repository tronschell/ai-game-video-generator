from string import Template

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided League of Legends gameplay clip to identify highlight moments featuring player "${username}".

    VARIABLES:
    - Player of Interest: "${username}"
    - Minimum Highlight Duration: ${min_highlight_duration_seconds} seconds

    OUTPUT REQUIREMENTS:
    - Output MUST be a JSON list of highlight objects.
    - Only if there are no kills, assists, or notable plays by "${username}" in the video at all, output an empty list [] or do not return anything.
    - In every video you analyze should have a highlight.
    - Each highlight object MUST contain:
        - "timestamp_start_seconds": number (integer, e.g., 55)
        - "timestamp_end_seconds": number (integer, e.g., 90)
        - "clip_description": string (e.g., "${username} gets a triple kill with Yasuo. CHECK1. kill 1 (56s, enemy Lux), kill 2 (65s, enemy Jinx), kill 3 (78s, enemy Leona).")
    - After a timestamp has been identified, replay this timestamp to ensure that we encapsulate the entire highlight and ensure it is accurate without missing any extra kills or plays.

    VIDEO PROCESSING INSTRUCTIONS:
    1. Analyze the entire video before identifying timestamps.
    2. Prioritize accuracy in identifying kills and assists by "${username}" based on the kill feed and game announcements.
    3. For videos with UI elements that might be misleading, focus on the kill feed and announcements to verify kills and assists.
    4. (CRITICAL) When watching each video, keep a count of number of kills made by "${username}" and its associated timestamp, the champion they're playing, and the enemy champion that was killed which can be found in the kill feed.
    5. (CRITICAL) Appended to the end of the clip_description, include the kill count timestamps for each kill from your memory. For example, "kill 1 (56s, enemy Lux), kill 2 (65s, enemy Jinx), kill 3 (78s, enemy Leona)."

    HIGHLIGHT IDENTIFICATION CRITERIA (Strictly Adhere):

    A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):
        1. Every and all kills made by "${username}". These are identifiable in the kill feed and announcements.
        2. Multi-kills (double kill, triple kill, quadra kill, penta kill) by "${username}".
        3. If multiple kills by "${username}" occur in rapid succession or a continuous action sequence, group them into a single highlight clip.
        4. Important assists in team fights that lead to multiple team kills.
        5. Epic monster steals (Baron, Dragon, Herald) by "${username}".
        6. Outplays where "${username}" survives a difficult situation while securing kills.

    B. TIMESTAMPING RULES (CRITICAL):
        1. All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
        2. Each individual highlight segment (from start buffer to end buffer) MUST be at least ${min_highlight_duration_seconds} seconds long. If a qualifying kill sequence with buffers is shorter, it should not be included unless it's part of a larger valid sequence.
        3. Add exactly a 2-second buffer BEFORE the first relevant action (e.g., first kill) in a highlight sequence.
        4. Add exactly a 2-second buffer AFTER the last relevant action (e.g., last kill) in a highlight sequence.
        5. If multiple distinct highlight-worthy action sequences by "${username}" occur but are separated by significant non-action periods, create separate highlight entries for each.

    C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following):
        1. Deaths or any moments where "${username}" is eliminated without securing any kills or assists.
        2. Spectator mode footage, unless "${username}" is clearly the player being spectated or involved in the highlighted play.
        3. Game end screens, unless they are an immediate part of the kill action sequence.
        4. Any toxic commentary, racist remarks, or trolling behavior visible or audible.

    D. CONTENT TO CUT OUT/SHORTEN:
        1. Any moments where "${username}" does not secure a kill or make a significant play. This includes:
            - General gameplay (farming, moving around the map).
            - Shopping/item buying phases.
            - Moments where "${username}" is dealing damage but does not confirm a kill (check kill feed).

    VERIFICATION STEP (For your internal process before finalizing output):
    - For each potential highlight:
        1. Confirm "${username}" is the one getting the kill(s) or making the play. This can be confirmed by checking the kill feed and game announcements. Include "CHECK1" in the `clip_description` to confirm this check.
        2. Verify the timestamp adheres to all buffer and minimum duration rules and please do not cut the highlight too short.
        3. Ensure no excluded content is present.
        4. After every other step is done, verify that there is no excessive downtime in the clip and that there's nothing important that happens immediately before or after the highlight. If there is excessive downtime, trim down the video to exclude those parts. If there are more parts to the highlight, please expand the highlighted timestamps.

    EXAMPLE HIGHLIGHT FORMAT:
    [
      {
        "timestamp_start_seconds": 55,
        "timestamp_end_seconds": 90,
        "clip_description": "${username} gets a triple kill with Yasuo. CHECK1. kill 1 (56s, enemy Lux), kill 2 (65s, enemy Jinx), kill 3 (78s, enemy Leona)."
      },
      {
        "timestamp_start_seconds": 100,
        "timestamp_end_seconds": 115,
        "clip_description": "${username} steals Baron Nashor with Jinx ultimate. CHECK1."
      }
    ]
    ''') 