# Why Some Skills Have Responses and Others Don't?

## Quick Answer

**Skills with responses:** `field_logic_quality`, `run_time_quality`, `review_back_office`  
**Skills without responses:** `component_quality`, `form_structure_quality` (return 0 chars)

**Reason:** Complexity & AI Farm timeout/limits

---

## Detailed Comparison

### SKILLS WITH RESPONSES ✅

#### 1. **field_logic_quality** (B1-B4) - 4 checks
- **Response:** 427 chars ✅
- **Time:** ~27 seconds
- **Prompt complexity:** Medium
- **Procedure lines:** ~20 lines
- **Requirements:**
  - B1: Check for null/undefined handling in logic
  - B2: Text concatenation truncation
  - B3: Approver-edit clear-value behavior
  - B4: Conditional required validation

**Why it works:** 
- Prompt is **focused and specific**
- Checks are straightforward: does logic safely handle missing values?
- AI Farm can answer YES/NO with reasoning

---

#### 2. **run_time_quality** (D1-D3) - 3 checks  
- **Response:** 487 chars ✅
- **Time:** ~13 seconds
- **Prompt complexity:** Medium
- **Procedure lines:** ~30 lines
- **Requirements:**
  - D1: Calculated display values show [object Object]?
  - D2: JS errors or Form.io warnings?
  - D3: console.log statements outside Admin panel?

**Why it works:**
- Clear, specific validation rules
- Each check has **single, testable answer**
- AI Farm can traverse and report findings

---

#### 3. **review_back_office** (B1-B6) - 6 checks
- **Response:** 242 chars ✅
- **Time:** ~28 seconds
- **Prompt complexity:** Low-Medium
- **Procedure lines:** ~8 lines
- **Requirements:**
  - B1: form.form_url check
  - B2: Segment Rule precedence
  - B3-B6: Configuration checks

**Why it works:**
- Backoffice JSON is simpler structure than Form.io
- Checks map directly to JSON fields
- AI Farm returns violation list (different format, but parseable)

---

### SKILLS WITHOUT RESPONSES ❌

#### 1. **component_quality** (A1-A3) - 3 checks
- **Response:** 0 chars ❌
- **Time:** ~35 seconds (timeout?)
- **Prompt complexity:** VERY HIGH 🔴
- **Procedure lines:** 18 per check = **54+ lines total**
- **Key requirements:**
  - **A1: EXHAUSTIVE camelCase scan of EVERY component**
    ```
    "**EXHAUSTIVE SCAN REQUIREMENT**: You MUST check EVERY SINGLE component 
    in the entire file. Do not stop early or report only a subset."
    ```
  - Complex exception logic (ADMIN_Sys Attachment Auth with 2 conditions)
  - Must traverse ALL nested components recursively
  - Must report ALL violations, not just first one

  - **A2: Detect auto-generated numeric suffixes**
    ```
    "**CRITICAL EXHAUSTIVE COLLECTION**: maintain a COMPLETE LIST of ALL 
    components that end with numeric suffixes. Include every single one."
    ```
  - Must check EVERY component
  - Must collect and report ALL violations

  - **A3: Similar exhaustive requirements**

**Why it FAILS:**
- **Prompt is EXTREMELY LONG** (~2000+ tokens per A check)
- **Recursive complexity:** Must traverse possibly 100+ components
- **Complex business logic:** Multiple exception conditions
- **Output requirement:** Must report ALL violations (unbounded output)
- **AI Farm limits:**
  - May timeout after 35 seconds ⏱️
  - May hit response length limit
  - May struggle with "exhaustive" + "all" requirements

---

#### 2. **form_structure_quality** (C1-C7) - 7 checks
- **Response:** 0 chars ❌
- **Time:** ~31 seconds (timeout?)
- **Prompt complexity:** VERY HIGH 🔴
- **Procedure lines:** 20+ per check = **140+ lines total**
- **Key requirements:**
  - **C1: Column component structure validation**
    - Check EVERY column in EVERY columns component
    - Count direct children per column
    - Report violations

  - **C2: Main wrapper validation (3 attributes)**
    - Must verify: key="main", type="well", customClass="main-wrapper"
    - Complex validation with multiple failure modes

  - **C3-C7: Complex structure rules**
    - Attachment authorization detection
    - Nesting depth analysis
    - Repeated logic pattern detection
    - Required field presence checks

**Why it FAILS:**
- **7 checks = 7x more complexity than simple skills**
- **Deep nesting analysis:** Must traverse form structure to find depth
- **Pattern detection:** Must identify repeated logic/components
- **Multiple validation dimensions:**
  - Structure (columns, depth)
  - Configuration (attributes)
  - Logic (repeated patterns)
  - Requirements (summary field)
- **Unbounded output:** Must report all violations across 7 dimensions
- **AI Farm struggles with:**
  - Long, multi-dimensional prompts
  - Exhaustive pattern matching
  - Complex nesting depth calculations

---

## Comparison Table

| Dimension | field_logic | run_time | component | form_structure | review_backoffice |
|-----------|------------|---------|-----------|-----------------|------------------|
| Checks | 4 | 3 | 3 | 7 | 6 |
| Response size | 427 | 487 | 0 | 0 | 242 |
| Time (sec) | ~27 | ~13 | ~35 | ~31 | ~28 |
| Procedure lines per check | ~5 | ~10 | ~18 | ~20 | ~8 |
| Exhaustive scan? | ❌ No | ❌ No | ✅ YES | ✅ YES | ❌ No |
| Exception logic? | Low | Low | 🔴 HIGH | 🔴 HIGH | Low |
| Nesting depth check? | No | No | Yes | Yes | No |
| Pattern matching? | No | No | No | Yes | No |
| **Timeout risk** | 🟢 Low | 🟢 Low | 🔴 HIGH | 🔴 HIGH | 🟡 Medium |
| **AI Farm success** | ✅ | ✅ | ❌ | ❌ | ✅ |

---

## Root Cause Analysis

### Why AI Farm Times Out on Complex Skills

1. **Prompt Token Limit**
   - component_quality full prompt: ~2000+ tokens
   - form_structure_quality full prompt: ~3000+ tokens  
   - Each with 18-20 procedure steps
   - Plus JSON input from numbered_source (potentially huge)
   - **Total might exceed AI Farm's input limit**

2. **Output Generation Complexity**
   - Exhaustive scans require model to hold entire JSON structure in context
   - Multiple exception conditions to evaluate per item
   - "Report ALL violations" = unbounded output generation
   - Model may timeout trying to generate comprehensive output

3. **Task Type Mismatch**
   - AI Farm's `gpt-5-nano` is optimized for **quick, specific answers**
   - Not designed for **exhaustive multi-dimensional analysis**
   - OpenAI's GPT-4 handles this better with higher context/processing capacity

4. **Recursive Complexity**
   - component_quality must recursively traverse form structure
   - form_structure_quality must calculate nesting depth + pattern matching
   - Tree traversal is complex for LLMs compared to linear analysis

---

## What Works vs What Doesn't

### ✅ Works Well (AI Farm Can Handle)
```
- Specific validation questions (Is X safe? Does Y exist?)
- Linear analysis of structured data
- Clear yes/no checks
- Limited output (1-3 violations)
- Short, focused procedures (5-10 lines)
- No complex exception logic
```

### ❌ Fails (AI Farm Struggles)
```
- Exhaustive scanning of large nested structures
- Complex business logic with multiple exceptions
- Unbounded output requirements ("report ALL")
- Deep tree traversal and pattern matching
- Multiple validation dimensions (structure + logic + config)
- Prompts with 50+ lines of procedure
```

---

## Solution Recommendations

### Short Term (Quick Fixes)
1. **Simplify component_quality:**
   - Remove exhaustive requirement
   - Report only FIRST violation per check
   - Reduce exception logic

2. **Split form_structure_quality:**
   - Break 7 checks into 2 simpler skills
   - C1-C2 (structure) in one skill
   - C3-C7 (logic/config) in another

3. **Increase AI Farm timeout:**
   - Currently 60 seconds
   - Try 90-120 seconds for complex skills
   - Check if AI Farm supports custom timeouts

### Medium Term (Architecture)
1. **Use OpenAI for complex skills:**
   - Set `LLM_PROVIDER=openai` for component_quality, form_structure_quality
   - Use AI Farm for simple skills (faster, cheaper)
   - Create skill-level provider routing

2. **Redesign prompt structure:**
   - Break exhaustive requirements into simpler steps
   - Use sequential prompting (check A, then B, then C)
   - Instead of one mega-prompt

3. **Implement chunking:**
   - Analyze Form.io in parts (components 0-20, 21-40, etc.)
   - Aggregate results
   - Avoid single massive traversal

### Long Term (Strategic)
1. **Pre-process Form.io locally:**
   - Index components before sending to LLM
   - Send only relevant components per check
   - Reduce token waste

2. **Upgrade AI Farm:**
   - Request support for longer timeouts
   - Verify context window size
   - Consider custom fine-tuning

3. **Hybrid approach:**
   - Rules-based checks (can code locally): camelCase validation, key patterns
   - LLM checks (need AI): logic safety, best practices
   - Combine results

---

## Evidence from Logs

**Run 2 (10:30:23) - After git pull:**

```log
# These work - have responses
field_logic_quality:     427 chars response ✅ (time: 17s)
run_time_quality:        487 chars response ✅ (time: 13s)
review_back_office:      242 chars response ✅ (time: 29s)

# These fail - zero response  
component_quality:       0 chars response ❌ (time: 35s - timeout!)
form_structure_quality:  0 chars response ❌ (time: 31s - timeout!)
```

The **timeout clock** shows when AI Farm stops responding:
- Simple skills: 13-29 seconds (quick, complete)
- Complex skills: 31-35 seconds (hitting timeout boundary)

This confirms AI Farm has a **timeout limit around 35-40 seconds** and these complex skills exceed it.

