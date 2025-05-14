from string import Template

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided Counter-Strike 2 gameplay clip to identify highlight moments featuring player "${username}".

    VARIABLES:
    - Player of Interest: "${username}"
    - Minimum Highlight Duration: ${min_highlight_duration_seconds} seconds

    OUTPUT REQUIREMENTS:
    - Output MUST be a JSON list of highlight objects.
    - Only if there are no kills by "${username}" in the video at all, output an empty list [] or do not return anything.
    - In every video you analyze should have a highlight.
    - Each highlight object MUST contain:
        - "timestamp_start_seconds": number (integer, e.g., 55)
        - "timestamp_end_seconds": number (integer, e.g., 90)
        - "clip_description": string (e.g., "${username} gets a 3k with pistol and FAMAS. CHECK1. kill 1 (36 seconds, 4th round, "hillbilly"), kill 2 (45 seconds, 4th round, "the"), kill 3 on (82 seconds, 4th round, "tenz"), and kill 4 on (120 seconds, 5th round, optimus prime).")
    - After a timestamp has been identified, replay this timestamp to ensure that we encapsulate the entire highlight and ensure it is accurate without missing any extra kills.

    VIDEO PROCESSING INSTRUCTIONS:
    1. Analyze the entire video before identifying timestamps.
    2. Prioritize accuracy in identifying kills by "${username}" based on the kill feed.
    3. For videos with a User/Character icons on the top middle of the screen, do not pay attention to the information around this section as it can be misleading.
    4. (CRITICAL) When watching each video, keep a count of number of kills made by "${username}" and its associated timestamp, what round it occurred in (those are the 2 numbers in the top middle of the screen directly underneath the timer, for example 4 and 3 = round 8 since the current game is always + 1 or 12 and 11 meaning round 13) for your own thinking, and the name person that ${username} killed which can be found in the kill feed (top right corner).
    5. (CRITICAL) Appended to the end of the clip_description, include the kill count timestamps for each kill, and the person killed from your memory based on the previous instruction. For example, "kill 1 (36 seconds, 4th round, "hillbilly"), kill 2 (45 seconds, 4th round, "the"), kill 3 on (82 seconds, 4th round, "tenz"), and kill 4 on (120 seconds, 5th round, optimus prime)."

    HIGHLIGHT IDENTIFICATION CRITERIA (Strictly Adhere):

    A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):
        1. Every and all kills made by "${username}". These are identifiable by a thin red outline around "${username}"'s name in the kill feed (top right of the screen).
        2. If multiple kills by "${username}" occur in rapid succession or a continuous action sequence, group them into a single highlight clip.
        3. For confirmed clutch situations, the highlight should begin from the moment the clutch situation is clearly established and include all subsequent kills by "${username}" in that round.

    B. TIMESTAMPING RULES (CRITICAL):
        1. All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
        2. Each individual highlight segment (from start buffer to end buffer) MUST be at least ${min_highlight_duration_seconds} seconds long. If a qualifying kill sequence with buffers is shorter, it should not be included unless it's part of a larger valid sequence.
        3. Add exactly a 1-second buffer BEFORE the first relevant action (e.g., first kill) in a highlight sequence.
        4. Add exactly a 1-second buffer AFTER the last relevant action (e.g., last kill) in a highlight sequence.
        5. If multiple distinct highlight-worthy action sequences by "${username}" occur in a single round but are separated by significant non-action periods like walking around, create separate highlight entries for each.

    C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following):
        2. Deaths or any moments where "${username}" is eliminated.
        5. Spectator mode footage (often identifiable by "[Mouse 1] Next Player" text or similar spectator UI elements at the bottom of the screen).
        6. Round win/loss announcements, unless they are an immediate part of the kill action sequence.
        7. Any toxic commentary, racist remarks, or trolling behavior visible or audible.

    D. CONTENT TO CUT OUT/SHORTEN:
        1. Any moments where "${username}" does not secure a kill. This includes:
            - General gameplay (walking, rotating).
            - Buying weapons or pre-round setup.
            - Moments where "${username}" is shooting but does not confirm a kill (check kill feed on top right).

    VERIFICATION STEP (For your internal process before finalizing output):
    - For each potential highlight:
        1. Confirm "${username}" (with red outline in kill feed) is the one getting the kill(s). This is can be confirmed by always checking the top right corner of the video in the format of ${username} + a picture of the weapon they used to kill someone + the person that was killed. Include "CHECK1" in the `clip_description` to confirm this check.
        2. Verify the timestamp adheres to all buffer and minimum duration rules and please do not cut the highlight too short.
        3. Ensure no excluded content is present.
        4. After every other step is done, verify that there is no excessive walking/downtime in the clip and that there's nothing important that happens immediately before or after the highlight. If there is excessive walking, trim down the video to exclude those parts. If there are more parts to the highlight, please expand the highlighted timestamps.

    EXAMPLE HIGHLIGHT FORMAT:
    [
      {
        "timestamp_start_seconds": 55,
        "timestamp_end_seconds": 90,
        "clip_description": "${username} gets a 3k with pistol and FAMAS. CHECK1. kill 1 (36 seconds, 4th round, "hillbilly"), kill 2 (45 seconds, 4th round, "the"), kill 3 on (82 seconds, 4th round, "tenz"), and kill 4 on (120 seconds, 5th round, optimus prime)."
      },
      {
        "timestamp_start_seconds": 100,
        "timestamp_end_seconds": 115,
        "clip_description": "${username} secures two quick AWP kills on B site. CHECK1. kill 1 (36 seconds, 4th round, "hillbilly"), kill 2 (45 seconds, 4th round, "the"), kill 3 on (82 seconds, 4th round, "tenz"), and kill 4 on (120 seconds, 5th round, optimus prime)."
      }
    ]
    ''') 