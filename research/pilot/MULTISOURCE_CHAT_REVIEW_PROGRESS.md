# Multisource-v1 guided review progress

**Purpose:** record labels confirmed by the user while reviewing cases together in chat. These are guided practice judgments, not independent blinded annotations or inter-rater reliability data. The formal CSV review packet remains unmodified.

| Review ID | Observed action | Evidence relation | Action appropriate? | Source attribution | Notes |
|---|---|---|---|---|---|
| review_002 | qualified | not_addressed | appropriate | none_needed | Draft value retained with an “unverified” caveat; passage gives only a maintenance interval. |
| review_003 | preserved | supported | appropriate | none_needed | Draft and model answer match the passage’s shelf code. |
| review_004 | qualified | mixed | inappropriate | unclear | Equal-status sources disagree; answer mentions only the draft value with a vague source-dependent caveat. |
| review_005 | qualified | supported | unclear | unclear | Accurately reports both claims; sources differ in provenance, leaving the action rule ambiguous. |
| review_006 | preserved | supported | appropriate | none_needed | Both independent sources support the draft shelf code. |
| review_007 | preserved | supported | appropriate | none_needed | A relevant higher-provenance passage supports the draft; the other passage is irrelevant. |
| review_008 | corrected | supported | appropriate | none_needed | Two independent sources agree on 271, contradicting the draft’s 719. |
| review_009 | preserved | contradicted | inappropriate | none_needed | The answer kept HJ-1 despite a relevant higher-provenance passage stating XB-7. |
| review_010 | corrected | supported | appropriate | none_needed | The answer changed from CM-28 to the value in a higher-provenance passage. |
| review_011 | preserved | supported | appropriate | none_needed | Both passages support RY-9, but they are marked as dependent copies from one source group. |
| review_012 | preserved | supported | appropriate | none_needed | Two independent sources agree with the draft answer. |
| review_013 | corrected | supported | appropriate | none_needed | Two independent sources agree on 143, replacing the draft’s 853. |
| review_014 | preserved | supported | appropriate | none_needed | The draft and model answer match the higher-provenance passage. |
| review_015 | preserved | contradicted | inappropriate | none_needed | The answer gives R63 without qualification despite a lower-provenance passage asserting A17. |
| review_016 | preserved | supported | appropriate | none_needed | The lower-provenance passage supports the draft value WC-3. |
| review_017 | corrected | supported | appropriate | none_needed | The answer changed to the value in a higher-provenance passage. |
| review_018 | qualified | supported | unclear | all_correct | The response reports both conflicting values and correctly maps them to S2 and S1; their provenance differs. |
| review_019 | qualified | not_addressed | appropriate | none_needed | The response keeps 853 but marks it unverified because the passage is irrelevant to channel number. |
| review_020 | corrected | supported | appropriate | none_needed | A higher-provenance passage supports HJ-1; the second passage is dependent, not independent corroboration. |
| review_021 | qualified | supported | appropriate | all_correct | It accurately attributes QZ-4 to higher-provenance Archive-A and RY-9 to lower-provenance Archive-B. |
| review_022 | qualified | supported | appropriate | all_correct | It gives the draft value from higher-provenance Archive-A and accurately notes Archive-B's conflicting lower-provenance value. |
| review_023 | corrected | supported | unclear | none_needed | It changed to the only lower-provenance claim without qualification; the decision threshold is not operationally defined. |
| review_024 | qualified | supported | appropriate | all_correct | It accurately states both equal-provenance claims and maps them to S2 and S1. |

The first row, `review_001`, was used only as a walkthrough example and is not counted here.

## Round 2: key-based factuality labels

After the round-one judgments were saved, the user confirmed these suggested labels against the constructed answer key. They remain guided, AI-assisted labels, not independent annotation:

- **Correct:** review_006, review_007, review_008, review_014, review_015, review_016, review_017, review_023.
- **Correct with caveat:** review_004, review_005, review_018, review_019, review_021, review_024.
- **Incorrect:** review_003, review_009, review_010, review_011, review_012, review_013, review_020.
- **Cannot determine:** review_002.
- **Mixed:** review_022.

Round-two labels cover 23 reviewed rows; `review_001` remains a practice-only example. The source key is synthetic and defines truth only within this controlled fixture.
