from string import Template

# This is a general-purpose template that can be used for any game.
# To create a custom prompt for a different game:
# 1. Copy this file and name it after your game (e.g., valorant.py)
# 2. Modify the template to match your game's specific needs
# 3. Import the new prompt in src/prompts/__init__.py
# 4. Add the game type to the PROMPT_TEMPLATES dictionary in __init__.py
# 5. Update your config.json to use the new game type

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided gameplay clip to identify highlight moments featuring player "${username}".

    VARIABLES:
    - Player of Interest: "${username}"
    - Minimum Highlight Duration: ${min_highlight_duration_seconds} seconds

    OUTPUT REQUIREMENTS:
    - Output MUST be a JSON list of highlight objects.
    - Only if there are no significant gameplay moments by "${username}" in the video at all, output an empty list [] or do not return anything.
    - In every video you analyze should have a highlight.
    - Each highlight object MUST contain:
        - "timestamp_start_seconds": number (integer, e.g., 55)
        - "timestamp_end_seconds": number (integer, e.g., 90)
        - "clip_description": string (e.g., "${username} gets three eliminations in quick succession. CHECK1.")
    - After a timestamp has been identified, replay this timestamp to ensure that we encapsulate the entire highlight and ensure it is accurate without missing any extra gameplay moments.

    VIDEO PROCESSING INSTRUCTIONS:
    1. Analyze the entire video before identifying timestamps.
    2. Prioritize accuracy in identifying significant gameplay moments by "${username}" based on the kill feed or game announcements.
    3. For videos with UI elements that might be misleading, focus on the gameplay action and feed to verify achievements.
    4. (CRITICAL) When watching each video, note timestamps of significant gameplay actions by "${username}".

    HIGHLIGHT IDENTIFICATION CRITERIA (Strictly Adhere):

    A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):
        1. Every and all eliminations/kills made by "${username}".
        2. If multiple eliminations by "${username}" occur in rapid succession or a continuous action sequence, group them into a single highlight clip.
        3. Especially impressive plays, trick shots, or skillful maneuvers.
        4. Game-winning or objective-securing plays.
        5. Any announced special achievements (multi-kills, killstreaks, etc.).

    B. TIMESTAMPING RULES (CRITICAL):
        1. All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
        2. Each individual highlight segment (from start buffer to end buffer) MUST be at least ${min_highlight_duration_seconds} seconds long. If a qualifying sequence with buffers is shorter, it should not be included unless it's part of a larger valid sequence.
        3. Add exactly a 2-second buffer BEFORE the first relevant action in a highlight sequence.
        4. Add exactly a 2-second buffer AFTER the last relevant action in a highlight sequence.
        5. If multiple distinct highlight-worthy action sequences by "${username}" occur but are separated by significant non-action periods, create separate highlight entries for each.

    C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following):
        1. Deaths or any moments where "${username}" is eliminated without securing any significant plays.
        2. Spectator mode footage, unless "${username}" is clearly the player being featured.
        3. Game end screens, unless they are an immediate part of the highlighted action sequence.
        4. Any toxic commentary, racist remarks, or trolling behavior visible or audible.

    D. CONTENT TO CUT OUT/SHORTEN:
        1. Any moments where "${username}" does not have gameplay impact. This includes:
            - General gameplay (moving around, non-action periods).
            - Setup or preparation phases.
            - Moments where "${username}" is not the focus of the gameplay.

    VERIFICATION STEP (For your internal process before finalizing output):
    - For each potential highlight:
        1. Confirm "${username}" is the one performing the significant action(s). Include "CHECK1" in the `clip_description` to confirm this check.
        2. Verify the timestamp adheres to all buffer and minimum duration rules and please do not cut the highlight too short.
        3. Ensure no excluded content is present.
        4. After every other step is done, verify that there is no excessive downtime in the clip and that there's nothing important that happens immediately before or after the highlight. If there is excessive downtime, trim down the video to exclude those parts. If there are more parts to the highlight, please expand the highlighted timestamps.

    EXAMPLE HIGHLIGHT FORMAT:
    [
      {
        "timestamp_start_seconds": 55,
        "timestamp_end_seconds": 90,
        "clip_description": "${username} gets three eliminations in quick succession. CHECK1."
      },
      {
        "timestamp_start_seconds": 100,
        "timestamp_end_seconds": 115,
        "clip_description": "${username} makes a game-winning play by securing the objective. CHECK1."
      }
    ]
    ''') 