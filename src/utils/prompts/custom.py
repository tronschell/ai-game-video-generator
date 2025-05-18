from string import Template

# This is a general-purpose template that can be used for any game.
# To create a custom prompt for a different game:
# 1. Copy this file and name it after your game (e.g., valorant.py)
# 2. Modify the template to match your game's specific needs
# 3. Import the new prompt in src/prompts/__init__.py
# 4. Add the game type to the PROMPT_TEMPLATES dictionary in __init__.py
# 5. Update your config.json to use the new game type

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided Counter-Strike 2 gameplay clip to identify highlight moments featuring player "${username}".
Your process will be two-staged: first, identify all kills by "${username}", and second, use this information to generate highlight clips. Remember that this video will ABSOLUTELY have a highlight but it's up to you to find it.

VARIABLES:
- Player of Interest: "${username}"
- Minimum Highlight Duration: ${min_highlight_duration_seconds} seconds

**CRITICAL TWO-STEP PROCESS FOR ANALYSIS:**

**STEP 1: Meticulous Kill Identification (Internal Analysis - For Your Processing)**
   Your *absolute first task* is to meticulously scan the entire video and create a comprehensive internal list of EVERY single kill made by "${username}". For each kill, note the following:
    1.  **Kill Timestamp (seconds):** The exact second the kill occurs, based on the kill feed.
    2.  **Victim Name:** The name of the player killed by "${username}", as shown in the kill feed.
    3.  **Round Number:** Determined by the two numbers in the top middle of the screen directly underneath the timer (e.g., 4 and 3 means round 8 (4+3+1); 0 and 0 means round 1).
    4.  **Weapon Used (Optional, for context):** If easily identifiable from the kill feed.

   **Instructions for Kill Identification:**
    - Prioritize accuracy. Kills by "${username}" are identifiable by a thin red outline around "${username}"'s name in the kill feed (top right of the screen). The format is typically: `${username}` [weapon_icon] `victim_name`.
    - You are processing the video at 1 frame per second (1fps).
    - For videos with User/Character icons on the top middle of the screen, do not pay attention to the information around this section as it can be misleading for kill identification (focus on the kill feed).
    - Maintain this internal list of all kills throughout your analysis. This list is the *foundation* for Step 2.

**STEP 2: Highlight Generation (Final JSON Output)**
   Based *solely* on the comprehensive list of kills you identified in STEP 1, generate the highlight clips.

   **OUTPUT REQUIREMENTS:**
    - Output MUST be a JSON list of highlight objects.
    - If there are NO kills by "${username}" in the entire video (based on your STEP 1 analysis), output an empty list `[]`.
    - Each highlight object MUST contain:
        - "timestamp_start_seconds": number (integer, e.g., 55)
        - "timestamp_end_seconds": number (integer, e.g., 90)
        - "clip_description": string. This description MUST:
            - Briefly summarize the action (e.g., "${username} gets a 3k with pistol and FAMAS.").
            - Include "CHECK1." to confirm you verified "${username}" made the kills (red outline in kill feed).
            - Detail EACH kill *within that specific highlight segment*, using the information gathered in STEP 1. Format: "kill 1 ([timestamp] seconds, [round_number] round, "[victim_name]"), kill 2 ([timestamp] seconds, [round_number] round, "[victim_name]"), ..."

   **HIGHLIGHT IDENTIFICATION CRITERIA (Apply to the kill list from STEP 1):**

    A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):
        1. Every sequence of one or more kills made by "${username}" (from your STEP 1 list).
        2. If multiple kills by "${username}" occur in rapid succession or as part of a continuous action sequence, group them into a single highlight clip.
        3. For confirmed clutch situations (e.g., "${username}" is the last player alive against multiple opponents), the highlight should begin from when the clutch is established and include all subsequent kills by "${username}" in that round from your STEP 1 list.

    B. TIMESTAMPING RULES (CRITICAL - Apply to each generated highlight):
        1. All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
        2. Use the kill timestamps from your STEP 1 list as the basis.
        3. Add exactly a 1-second buffer BEFORE the timestamp of the *first kill* in a highlight sequence.
        4. Add exactly a 1-second buffer AFTER the timestamp of the *last kill* in a highlight sequence.
        5. Each individual highlight segment (from start buffer to end buffer) MUST be at least ${min_highlight_duration_seconds} seconds long. If a qualifying kill sequence with buffers is shorter, it should not be included UNLESS it's a single, very impactful kill that, with buffers, meets the duration. If it still doesn't, try to group it with another nearby kill if logical, otherwise omit.
        6. If multiple distinct highlight-worthy action sequences by "${username}" (based on your STEP 1 kill list) occur in a single round but are separated by significant non-action periods (e.g., more than 10-15 seconds of just walking, rotating without engagement), create separate highlight entries for each.

    C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following in the final highlight clips):
        1. Deaths or any moments where "${username}" is eliminated.
        2. Spectator mode footage (often identifiable by "[Mouse 1] Next Player" text or similar spectator UI elements at the bottom of the screen).
        3. Round win/loss announcements, unless they are an immediate part of the kill action sequence.
        4. Any toxic commentary, racist remarks, or trolling behavior visible or audible.

    D. CONTENT TO CUT OUT/SHORTEN FROM HIGHLIGHTS (Refine segment boundaries):
        1. Trim any excessive periods where "${username}" is not actively engaged in or immediately leading up to/following up on kills from your STEP 1 list. This includes:
            - General gameplay (walking, rotating) NOT directly connecting kills in a sequence.
            - Buying weapons or pre-round setup (unless a kill happens immediately after).
            - Moments where "${username}" is shooting but does not confirm a kill (not on your STEP 1 list).

   **VERIFICATION STEP (Internal check before finalizing JSON output):**
    - For each potential highlight generated from your STEP 1 kill list:
        1. Confirm "${username}" (with red outline in kill feed) is the one getting the kill(s) for all kills listed in the `clip_description`. (This is the CHECK1 confirmation).
        2. Verify the `timestamp_start_seconds` and `timestamp_end_seconds` adhere to all buffer rules (B.3, B.4) and the `min_highlight_duration_seconds` (B.5). Ensure highlights are not cut too short and fully encapsulate the action based on the kill timestamps.
        3. Ensure no excluded content (C) is present.
        4. Re-evaluate the segment: Is there excessive walking/downtime *within* the highlight? Trim it. Is there an important action (another kill by ${username} from your STEP 1 list) immediately before the start or after the end that should be included? Expand the timestamps to include it, respecting buffer rules.

EXAMPLE HIGHLIGHT FORMAT (Based on your STEP 1 analysis):
[
  {
    "timestamp_start_seconds": 35,
    "timestamp_end_seconds": 84,
    "clip_description": "${username} gets a 3k with pistol and FAMAS. CHECK1. kill 1 (36 seconds, 4th round, \"hillbilly\"), kill 2 (45 seconds, 4th round, \"the\"), kill 3 (82 seconds, 4th round, \"tenz\")."
  },
  {
    "timestamp_start_seconds": 119,
    "timestamp_end_seconds": 130, // Assuming min_duration allows for this if it was e.g. a 9 sec kill + 2s buffer
    "clip_description": "${username} gets a crucial opening pick. CHECK1. kill 1 (120 seconds, 5th round, \"optimus prime\")."
  }
]
    ''') 