
Paste the entire block below into it and save.

---

```powershell
# mammoth-notes-upgrade.ps1
# MammothOS Agent System Notes Upgrade
# Delegates all code generation to MammothOS agents (AtlasAgent + CodingAgent)
# Run:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#       .\mammoth-notes-upgrade.ps1

param(
    [string]$WorkspaceRoot = "C:\Users\runni\mammoth_intro_ai.worktrees
# Run:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#       .\mammoth-notes-upgrade.ps1

param(
    [string]$WorkspaceRoot = "C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system"
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BASE_URL  = "http://localhost:8000"
$NOTES_DIR = "ui/mad-architecht-command-center/src/notes"

# ------------------------------------------------------------------ helpers --
function Write-Step { param($m); Write-Host "`n--- $m ---" -ForegroundColor Cyan }
function Write-OK   \agents-mammothos-atlas-agent-system"
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BASE_URL  = "http://localhost:8000"
$NOTES_DIR = "ui/mad-architecht-command-center/src/notes"

# ------------------------------------------------------------------ helpers --
function Write-Step { param($m); Write-Host "`n--- $m ---" -ForegroundColor Cyan }
function Write-OK   { param($m); Write-Host "[OK]   $m"   -ForegroundColor Green }
function Write-Fail { param($m); Write-Host "[FAIL] $m"   -ForegroundColor Red }
function Write-Info { param($m); Write-Host "[INFO] $m"   -ForegroundColor Yellow }

function Read-SrcFile {
    param([string]$RelPath)
    $full = Join-Path ${ param($m); Write-Host "[OK]   $m"   -ForegroundColor Green }
function Write-Fail { param($m); Write-Host "[FAIL] $m"   -ForegroundColor Red }
function Write-Info { param($m); Write-Host "[INFO] $m"   -ForegroundColor Yellow }

function Read-SrcFile {
    param([string]$RelPath)
    $full = Join-Path $WorkspaceRoot $RelPath
    if (Test-Path $full) { return (Get-Content $full -Raw) }
    return ""
}

# POST /agent/<name>/run  using query-param  ?payload=<urlencoded-json>
function Invoke-Agent {
    param([string]$AgentName, [string]$Prompt)
    $objWorkspaceRoot $RelPath
    if (Test-Path $full) { return (Get-Content $full -Raw) }
    return ""
}

# POST /agent/<name>/run  using query-param  ?payload=<urlencoded-json>
function Invoke-Agent {
    param([string]$AgentName, [string]$Prompt)
    $obj     = @{ prompt = $Prompt }
    $json    = $obj | ConvertTo-Json -Compress -Depth 5
    $encoded = [System.Uri]::EscapeDataString($json)
    $url     = "$BASE_URL/agent/$AgentName/run?payload=$encoded"
    Write-Info "Calling /$AgentName agent     = @{ prompt = $Prompt }
    $json    = $obj | ConvertTo-Json -Compress -Depth 5
    $encoded = [System.Uri]::EscapeDataString($json)
    $url     = "$BASE_URL/agent/$AgentName/run?payload=$encoded"
    Write-Info "Calling /$AgentName agent  (prompt length: $($Prompt.Length) chars)..."
    return (Invoke-RestMethod -Uri $url -Method POST -TimeoutSec 180)
}

# Walk common output-field  (prompt length: $($Prompt.Length) chars)..."
    return (Invoke-RestMethod -Uri $url -Method POST -TimeoutSec 180)
}

# Walk common output-field names to find agent text
function Get-AgentText {
    param($Resp)
    if ($null -eq $Resp) { return $null }
    foreach ($field in @("result","output","content","message","text","response")) {
        if ($Resp.PSObject.Properties[$field]) {
            $v = $Resp.$field
            if ($v -is [string] -and $v.Length -gt 0) { return names to find agent text
function Get-AgentText {
    param($Resp)
    if ($null -eq $Resp) { return $null }
    foreach ($field in @("result","output","content","message","text","response")) {
        if ($Resp.PSObject.Properties[$field]) {
            $v = $Resp.$field
            if ($v -is [string] -and $v.Length -gt 0) { return $v }
            if ($v -isnot [string] -and $null -ne $v) {
                foreach ($inner in @("output","content","text","result")) {
                    if ($v.PSObject.Properties[$inner]) { return $v.$inner }
                }
                return ($v | ConvertTo-Json -Depth 10)
            }
        }
    }
    return ($ $v }
            if ($v -isnot [string] -and $null -ne $v) {
                foreach ($inner in @("output","content","text","result")) {
                    if ($v.PSObject.Properties[$Resp | ConvertTo-Json -Depth 10)
}

# POST /api/atlas/apply  with JSON body to write a file
function Write-AgentFile {
    param([string]$RelPath, [string]$Content)
    $body = @{ operation = "write_file"; file_path = $RelPath; content = $Content }inner]) { return $v.$inner }
                }
                return ($v | ConvertTo-Json -Depth 10)
            }
        }
    }
    return ($Resp | ConvertTo-Json -Depth 10)
}

# POST /api/atlas/apply  with JSON body to write a file
function Write-AgentFile {
    param([string]$RelPath, [string]$Content)
    $body = @{ operation = "write_file"; file_path = $RelPath; content = $Content } `
           | ConvertTo-Json -Depth 3
    return (Invoke-RestMethod -Uri "$BASE_URL/api/atlas/apply" `
        -Method POST -ContentType "application/json" -Body $body -TimeoutSec 30)
}

# Parse  ===FILE: path===   `
           | ConvertTo-Json -Depth 3
    return (Invoke-RestMethod -Uri "$BASE_URL/api/atlas/apply" `
        -Method POST -ContentType "application/json" -Body $body -TimeoutSec 30)
}

# Parse  ===FILE: path===  ...content...  ===FILE:  or  ===END===
function Parse-FileBlocks {
    param([string]$Text)
    $files   = @{}
    $pattern = '===FILE:\s*([^\r\n]+?)\s*===\s*([\s\S]+?)(?====FILE:|===END===|\z)'
    foreach ($m in [regex]::Matches($Text, $pattern)) {
        $path    = $m.Groups[1].Value.Trim()
        $...content...  ===FILE:  or  ===END===
function Parse-FileBlocks {
    param([string]$Text)
    $files   = @{}
    $pattern = '===FILE:\s*([^\r\n]+?)\s*===\s*([\s\S]+?)(?====FILE:|===END===|\z)'
    foreach ($m in [regex]::Matches($Text, $pattern)) {
        $path    = $m.Groups[1].Value.Trim()
        $content = $m.Groups[2].Value.Trim()
        # strip optional markdown fences
        $content = [regex]::Replace($content, '^```[a-z]*\r?\n', '')
        $content = [regex]::Replace($content, '\r?\n```\s*$', '')
        $files[$path] = $content
    }
    return $files
}

# ============content = $m.Groups[2].Value.Trim()
        # strip optional markdown fences
        $content = [regex]::Replace($content, '^```[a-z]*\r?\n', '')
        $content = [regex]::Replace($content, '\r?\n```\s*$', '')
        $files[$path] = $content
    }
    return $files
}

# ============================================================ Step 0: health =
Write-Step "Step 0: Server health check"
try {
    $h = Invoke-RestMethod -Uri "$BASE_URL/health" -Method GET -TimeoutSec 10 -ErrorAction SilentlyContinue
    Write-OK "Server up: $($h | ConvertTo-Json -Compress)"
} catch {
    Write-Info "Health================================================ Step 0: health =
Write-Step "Step 0: Server health check"
try {
    $h = Invoke-RestMethod -Uri "$BASE_URL/health" -Method GET -TimeoutSec 10 -ErrorAction SilentlyContinue
    Write-OK "Server up: $($h | ConvertTo-Json -Compress)"
} catch {
    Write-Info "Health endpoint not found -- continuing anyway (server may still be up)."
}

# Verify agent routes exist
try {
    $_ = Invoke-RestMethod -Uri "$BASE_URL/agent/atlas/run? endpoint not found -- continuing anyway (server may still be up)."
}

# Verify agent routes exist
try {
    $_ = Invoke-RestMethod -Uri "$BASE_URL/agent/atlas/run?payload=%7B%22prompt%22%3A%22ping%22%7D" `
        -Method POST -TimeoutSec 15 -ErrorAction Stop
    Write-OK "Agent route reachable."
} catch {
    $msg = $_.Exception.Message
    if ($msg -match "400|422|500") {
        Write-OK "Agent route repayload=%7B%22prompt%22%3A%22ping%22%7D" `
        -Method POST -TimeoutSec 15 -ErrorAction Stop
    Write-OK "Agent route reachable."
} catch {
    $msg = $_.Exception.Message
    if ($msg -match "400|422|500") {
        Write-OK "Agent route reachable (expected error on ping: $msg)."
    } else {
        Write-Fail "Cannot reach agent route: $msg"
        Write-Fail "Make sure the MammothOS server is running on port 8000."
        achable (expected error on ping: $msg)."
    } else {
        Write-Fail "Cannot reach agent route: $msg"
        Write-Fail "Make sure the MammothOS server is running on port 8000."
        exit 1
    }
}

# ======================================================== Step 1: read files =
Write-Step "Step 1: Reading existing Notes source files"

$srcPanel       = Read-SrcFile "$NOTES_DIR/NotesPanel.tsx"
$srcList        = Read-SrcFile "$NOTES_DIR/NotesList.tsx"
$srcComposer    = Read-SrcFile "$NOTES_DIR/NotesComposerexit 1
    }
}

# ======================================================== Step 1: read files =
Write-Step "Step 1: Reading existing Notes source files"

$srcPanel       = Read-SrcFile "$NOTES_DIR/NotesPanel.tsx"
$srcList        = Read-SrcFile "$NOTES_DIR/NotesList.tsx"
$srcComposer    = Read-SrcFile "$NOTES_DIR/NotesComposer.tsx"
$srcNoteRecord  = Read-SrcFile "$NOTES_DIR/types/NoteRecord.ts"
$srcUseNotes    = Read-SrcFile "$NOTES_DIR/hooks/useAgentNotes.ts"
$srcUseCreate   = Read-SrcFile "$NOTES_DIR/hooks/useCreateNote.ts"
$srcUseDelete   = Read-SrcFile "$NOTES_DIR/hooks/useDeleteNote.ts.tsx"
$srcNoteRecord  = Read-SrcFile "$NOTES_DIR/types/NoteRecord.ts"
$srcUseNotes    = Read-SrcFile "$NOTES_DIR/hooks/useAgentNotes.ts"
$srcUseCreate   = Read-SrcFile "$NOTES_DIR/hooks/useCreateNote.ts"
$srcUseDelete   = Read-SrcFile "$NOTES_DIR/hooks/useDeleteNote.ts"

Write-OK "All existing files read."

# ==================================================== Step 2: AtlasAgent plan =
Write-Step "Step 2: AtlasAgent -- architecture planning"

$atlasPrompt = "You are the MammothOS AtlasAgent.`n`n" +
"TASK: Plan the upgrade of the Notes page to full Agent System Notes support.`n`n" +
"EXISTING STRUCTURE:`n" +
"- NotesPanel"

Write-OK "All existing files read."

# ==================================================== Step 2: AtlasAgent plan =
Write-Step "Step 2: AtlasAgent -- architecture planning"

$atlasPrompt = "You are the MammothOS AtlasAgent.`n`n" +
"TASK: Plan the upgrade of the Notes page to full Agent System Notes support.`n`n" +
"EXISTING STRUCTURE:`n" +
"- NotesPanel.tsx     (root panel, wraps NotesList + NotesComposer)`n" +
"- NotesList.tsx      (renders list; each note has: id, agent_id, type, content, priority, created_at, subsystem, metadata)`n" +.tsx     (root panel, wraps NotesList + NotesComposer)`n" +
"- NotesList.tsx      (renders list; each note has: id, agent_id, type, content, priority, created_at, subsystem, metadata)`n" +
"- NotesComposer.tsx  (simple text input + Create Note button)`n" +
"- types/NoteRecord.ts (Zod schema)`n" +
"- hooks/useAgentNotes.ts, useCreateNote.ts, useDeleteNote.ts`n`n" +
"AGENT NOTE TYPES TO SUPPORT:`n" +
"agent_approval, agent_request, agent_recommendation,`n" +
"agent_runtime, agent_workflow_summary, agent_safety
"- NotesComposer.tsx  (simple text input + Create Note button)`n" +
"- types/NoteRecord.ts (Zod schema)`n" +
"- hooks/useAgentNotes.ts, useCreateNote.ts, useDeleteNote.ts`n`n" +
"AGENT NOTE TYPES TO SUPPORT:`n" +
"agent_approval, agent_request, agent_recommendation,`n" +
"agent_runtime, agent_workflow_summary, agent_safety_notice,`n" +
"agent_plan_execute, agent_rollback`n`n" +
"REQUIREMENTS:`n" +
"1. New file: types/agentNoteTypes.ts -- AgentNoteType union, badge_notice,`n" +
"agent_plan_execute, agent_rollback`n`n" +
"REQUIREMENTS:`n" +
"1. New file: types/agentNoteTypes.ts -- AgentNoteType union, badge color/label/icon maps`n" +
"2. New file: components/AgentNoteBadge.tsx -- colored pill badge per note type`n" +
"3. Upgrade NotesList.tsx -- show badge, priority chip, subsystem, agent_id, created_at; group by type`n" +
"4. Upgrade NotesComposer.tsx -- dropdowns for type (all 8), priority (low/medium/high/critical), subsystem, agent_id fields color/label/icon maps`n" +
"2. New file: components/AgentNoteBadge.tsx -- colored pill badge per note type`n" +
"3. Upgrade NotesList.tsx -- show badge, priority chip, subsystem, agent_id, created_at; group by type`n" +
"4. Upgrade NotesComposer.tsx -- dropdowns for type (all 8), priority (low/medium/high/critical), subsystem, agent_id fields`n" +
"5. Upgrade NotesPanel.tsx -- filter bar (by type, priority, subsystem), search input, empty state message`n" +
"6. Upgrade hooks/useCreateNote.ts -- accept {content, type, priority, subsystem, agent_id}`n" +
"7. Preserve`n" +
"5. Upgrade NotesPanel.tsx -- filter bar (by type, priority, subsystem), search input, empty state message`n" +
"6. Upgrade hooks/useCreateNote.ts -- accept {content, type, priority, subsystem, agent_id}`n" +
"7. Preserve all existing mammoth-dark/mammoth-accent Tailwind tokens`n" +
"8. All interactive elements: hover: and focus-visible:ring-2 focus-visible:ring-mammoth-accent`n`n" +
"Return a concise numbered architecture plan. No code -- just the plan."

$atlasResp = Invoke-Agent -AgentName "atlas" -Prompt $atlasPrompt
if ($null -eq all existing mammoth-dark/mammoth-accent Tailwind tokens`n" +
"8. All interactive elements: hover: and focus-visible:ring-2 focus-visible:ring-mammoth-accent`n`n" +
"Return a concise numbered architecture plan. No code -- just the plan."

$atlasResp = Invoke-Agent -AgentName "atlas" -Prompt $atlasPrompt
if ($null -eq $atlasResp) {
    Write-Fail "AtlasAgent returned null. Aborting."
    exit 1
}
$atlasPlan = Get-AgentText -Response $atlasResp
if ([string]::IsNullOrWhiteSpace($atlasPlan)) {
    Write-Fail "AtlasAgent returned empty text. Aborting."
    exit 1
}
Write-OK "AtlasAgent plan received ($ $atlasResp) {
    Write-Fail "AtlasAgent returned null. Aborting."
    exit 1
}
$atlasPlan = Get-AgentText -Response $atlasResp
if ([string]::IsNullOrWhiteSpace($atlasPlan)) {
    Write-Fail "AtlasAgent returned empty text. Aborting."
    exit 1
}
Write-OK "AtlasAgent plan received ($($atlasPlan.Length) chars)."
Write-Host $atlasPlan -ForegroundColor Gray

# ================================================== Step 3: CodingAgent impl =
Write-Step "Step 3: CodingAgent -- generating upgraded files"

$codingPrompt = "You are the MammothOS CodingAgent. Generate all upgraded Notes components.`n`n" +
"ARCHITECTURE PLAN:`n" + $atlasPlan +($atlasPlan.Length) chars)."
Write-Host $atlasPlan -ForegroundColor Gray

# ================================================== Step 3: CodingAgent impl =
Write-Step "Step 3: CodingAgent -- generating upgraded files"

$codingPrompt = "You are the MammothOS CodingAgent. Generate all upgraded Notes components.`n`n" +
"ARCHITECTURE PLAN:`n" + $atlasPlan + "`n`n" +
"--- EXISTING: NotesPanel.tsx ---`n" + $srcPanel + "`n`n" +
"--- EXISTING: NotesList.tsx ---`n" + $srcList + "`n`n" +
"--- EXISTING: NotesComposer.tsx ---`n" + $srcComposer + "` "`n`n" +
"--- EXISTING: NotesPanel.tsx ---`n" + $srcPanel + "`n`n" +
"--- EXISTING: NotesList.tsx ---`n" + $srcList + "`n`n" +
"--- EXISTING: NotesComposer.tsx ---`n" + $srcComposer + "`n`n" +
"--- EXISTING: types/NoteRecord.ts ---`n" + $srcNoteRecord + "`n`n" +
"--- EXISTING: hooks/useAgentNotes.ts ---`n" + $srcUseNotes + "`n`n" +
"--- EXISTING: hooks/useCreateNote.ts ---`n" + $srcUseCreate + "`n`n" +
"--- EXISTING: hooks/useDeleteNote.ts ---`n" + $srcUseDelete + "`n`n" +
"MAMMOTHOS TAILWIND TOKENS:`n" +n`n" +
"--- EXISTING: types/NoteRecord.ts ---`n" + $srcNoteRecord + "`n`n" +
"--- EXISTING: hooks/useAgentNotes.ts ---`n" + $srcUseNotes + "`n`n" +
"--- EXISTING: hooks/useCreateNote.ts ---`n" + $srcUseCreate + "`n`n" +
"--- EXISTING: hooks/useDeleteNote.ts ---`n" + $srcUseDelete + "`n`n" +
"MAMMOTHOS TAILWIND TOKENS:`n" +
"  bg-mammoth-dark  bg-mammoth-dark/60  bg-mammoth-dark/40`n" +
"  border-mammoth-accent/40  border-mammoth-accent/
"  bg-mammoth-dark  bg-mammoth-dark/60  bg-mammoth-dark/40`n" +
"  border-mammoth-accent/40  border-mammoth-accent/30`n" +
"  shadow-neon  shadow-neon-sm  shadow-neon-xs`n" +
"  text-mammoth-accent  text-mammoth-light  font-mammoth-ui`n" +
"  bg-mammoth-accent hover:bg-mammoth-accent-light text-black font-semibold`n" +30`n" +
"  shadow-neon  shadow-neon-sm  shadow-neon-xs`n" +
"  text-mammoth-accent  text-mammoth-light  font-mammoth-ui`n" +
"  bg-mammoth-accent hover:bg-mammoth-accent-light text-black font-semibold`n" +
"  focus:ring-2 focus:ring-mammoth-accent  focus-visible:ring-2 focus-visible:ring-mammoth-accent`n" +
"  rounded-xl  rounded-md  rounded-lg
"  focus:ring-2 focus:ring-mammoth-accent  focus-visible:ring-2 focus-visible:ring-mammoth-accent`n" +
"  rounded-xl  rounded-md  rounded-lg  gap-1 gap-2 gap-4 p-4 p-3`n`n" +
"BADGE COLOR MAP (use these Tailwind classes on badge bg/text/border):`n" +
"  agent_approval:  gap-1 gap-2 gap-4 p-4 p-3`n`n" +
"BADGE COLOR MAP (use these Tailwind classes on badge bg/text/border):`n" +
"  agent_approval:         bg-green-500/20  text-green-400  border-green-500/40`n" +
"  agent_request:          bg-blue-500/20   text-blue-400   border-blue-500/40`n" +
"  agent_recommendation:   bg-purple-500/20 text-purple-400 border         bg-green-500/20  text-green-400  border-green-500/40`n" +
"  agent_request:          bg-blue-500/20   text-blue-400   border-blue-500/40`n" +
"  agent_recommendation:   bg-purple-500/20 text-purple-400 border-purple-500/40`n" +
"  agent_runtime:          bg-yellow-500/20 text-yellow-400 border-yellow-500/40`n" +
"  agent_workflow_summary: bg-cyan-500/20   text-cyan-400   border-cyan-500/40`n" +
"  agent_safety_notice:    bg-red-500/20    text-red-400    border-red-500/40`n" +
"  agent_plan_execute:     bg-orange-500/20 text-orange-400 border-orange-500/40`n" +
"  agent-purple-500/40`n" +
"  agent_runtime:          bg-yellow-500/20 text-yellow-400 border-yellow-500/40`n" +
"  agent_workflow_summary: bg-cyan-500/20   text-cyan-400   border-cyan-500/40`n" +
"  agent_safety_notice:    bg-red-500/20    text-red-400    border-red-500/40`n" +
"  agent_plan_execute:     bg-orange-500/20 text-orange-400 border-orange-500/40`n" +
"  agent_rollback:         bg-rose-500/20   text-rose-400   border-rose-500/40`n`n" +
"OUTPUT FORMAT -- output ONLY these blocks, nothing else:`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/types/agentNoteTypes.ts===`n" +
"<full TypeScript content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/components/AgentNoteBadge.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesList.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesComposer.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesPanel.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/hooks/useCreateNote.ts===`n" +
"<full TypeScript content>`n" +
"===END===`n`n" +
"CONSTRAINTS:`n" +
"- TypeScript + React functional components, no class components`n" +
"- Relative imports only (no @ aliases)`n" +
"- useCreateNote onCreate_rollback:         bg-rose-500/20   text-rose-400   border-rose-500/40`n`n" +
"OUTPUT FORMAT -- output ONLY these blocks, nothing else:`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/types/agentNoteTypes.ts===`n" +
"<full TypeScript content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/components/AgentNoteBadge.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesList.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesComposer.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/NotesPanel.tsx===`n" +
"<full TSX content>`n" +
"===FILE: ui/mad-architecht-command-center/src/notes/hooks/useCreateNote.ts===`n" +
"<full TypeScript content>`n" +
"===END===`n`n" +
"CONSTRAINTS:`n" +
"- TypeScript + React functional components, no class components`n" +
"- Relative imports only (no @ aliases)`n" +
"- useCreateNote onCreate: (args:{content:string;type:AgentNoteType;priority:string;subsystem:string;agent_id:string}) => Promise<void>`n" +
"- NotesComposer receives that onCreate prop: (args:{content:string;type:AgentNoteType;priority:string;subsystem:string;agent_id:string}) => Promise<void>`n" +
"- NotesComposer receives that onCreate prop`n" +
"- NotesPanel filters in-memory before passing notes to NotesList`n" +
"- Every select/input/button must have focus-visible:ring-2 focus-visible:ring-mammoth-accent`n" +
"- No explanations outside the ===FILE:=== blocks"

$coding`n" +
"- NotesPanel filters in-memory before passing notes to NotesList`n" +
"- Every select/input/button must have focus-visible:ring-2 focus-visible:ring-mammoth-accent`n" +
"- No explanations outside the ===FILE:=== blocks"

$codingResp = Invoke-Agent -AgentName "coding" -Prompt $codingPrompt
if ($null -eq $codingResp) {
    Write-Fail "CodingAgent returned null. Aborting."
    exit 1
}
$codingText = Get-AgentText -Response $codingResp
if ([string]::IsNullOrWhiteSpace($codingText)) {
    WriteResp = Invoke-Agent -AgentName "coding" -Prompt $codingPrompt
if ($null -eq $codingResp) {
    Write-Fail "CodingAgent returned null. Aborting."
    exit 1
}
$codingText = Get-AgentText -Response $codingResp
if ([string]::IsNullOrWhiteSpace($codingText)) {
    Write-Fail "CodingAgent returned empty text. Aborting."
    exit 1
}
Write-OK "CodingAgent response received ($($codingText.Length) chars)."

# ================================================ Step 4: parse file blocks =
Write-Step "Step 4: Parsing ===FILE:=== blocks"

$fileBlocks = Parse-FileBlocks -Text $codingText

if ($fileBlocks.Count -eq 0) {
    Write-Fail "No ===FILE:=== blocks found. Dumping raw output-Fail "CodingAgent returned empty text. Aborting."
    exit 1
}
Write-OK "CodingAgent response received ($($codingText.Length) chars)."

# ================================================ Step 4: parse file blocks =
Write-Step "Step 4: Parsing ===FILE:=== blocks"

$fileBlocks = Parse-FileBlocks -Text $codingText

if ($fileBlocks.Count -eq 0) {
    Write-Fail "No ===FILE:=== blocks found. Dumping raw output for inspection:"
    Write-Host "=== CodingAgent raw output ===" -ForegroundColor Magenta
    Write-Host $codingText
    Write-Host "=== end ===" -ForegroundColor Magenta
    Write for inspection:"
    Write-Host "=== CodingAgent raw output ===" -ForegroundColor Magenta
    Write-Host $codingText
    Write-Host "=== end ===" -ForegroundColor Magenta
    Write-Fail "Retry or inspect agent output above. Nothing was written."
    exit 1
}

Write-OK "Parsed $($fileBlocks.Count) file(s):"-Fail "Retry or inspect agent output above. Nothing was written."
    exit 1
}

Write-OK "Parsed $($fileBlocks.Count) file(s):"
foreach ($k in $fileBlocks.Keys) { Write-Host "    $k" -ForegroundColor Gray }

# ================================================ Step 5: write files =
Write-Step "Step 5: Writing files via /api/atlas/apply"

$written = 0
foreach ($filePath in $fileBlocks.Keys) {
    $content = $fileBlocks[$filePath]
    Write-Info "Writing: $filePath  ($($content.Length) chars)"
    try {
        $null
foreach ($k in $fileBlocks.Keys) { Write-Host "    $k" -ForegroundColor Gray }

# ================================================ Step 5: write files =
Write-Step "Step 5: Writing files via /api/atlas/apply"

$written = 0
foreach ($filePath in $fileBlocks.Keys) {
    $content = $fileBlocks[$filePath]
    Write-Info "Writing: $filePath  ($($content.Length) chars)"
    try {
        $null = Write-AgentFile -RelPath $filePath -Content $content
        Write-OK "Written: $filePath"
        $written++
    } catch {
        Write-Fail "Failed to write $filePath  --  $_"
        exit 1
    }
}

# ================================================ Step 6: git commit =
Write-Step "Step 6: Git commit"

$gitCmd  = "git add -A && git commit -m " +
           "' = Write-AgentFile -RelPath $filePath -Content $content
        Write-OK "Written: $filePath"
        $written++
    } catch {
        Write-Fail "Failed to write $filePath  --  $_"
        exit 1
    }
}

# ================================================ Step 6: git commit =
Write-Step "Step 6: Git commit"

$gitCmd  = "git add -A && git commit -m " +
           "'feat(notes): Agent System Notes upgrade -- 8 note types, badge system, composer fields, filter bar'"
$gitBody = @{ cmdfeat(notes): Agent System Notes upgrade -- 8 note types, badge system, composer fields, filter bar'"
$gitBody = @{ cmd = $gitCmd } | ConvertTo-Json -Compress

try {
    $gitResp = Invoke-RestMethod -Uri "$BASE_URL/api/terminal/exec" `
        -Method POST -ContentType "application/json" -Body $gitBody -TimeoutSec 30
    Write-OK "Git commit complete."
    Write-Host ($gitResp | ConvertTo-Json -Depth 5) -ForegroundColor Gray
} catch {
    Write-Fail "Git commit failed = $gitCmd } | ConvertTo-Json -Compress

try {
    $gitResp = Invoke-RestMethod -Uri "$BASE_URL/api/terminal/exec" `
        -Method POST -ContentType "application/json" -Body $gitBody -TimeoutSec 30
    Write-OK "Git commit complete.": $_"
    Write-Info "Files were written successfully. Commit manually with:"
    Write-Host "  git add -A" -ForegroundColor White
    Write-Host "  git commit -m 'feat(notes): Agent System Notes upgrade
    Write-Host ($gitResp | ConvertTo-Json -Depth 5) -ForegroundColor Gray
} catch {
    Write-Fail "Git commit failed: $_"
    Write-Info "Files were written successfully. Commit manually with:"
    Write-Host "  git add -A" -ForegroundColor White
    Write-Host "  git commit -m 'feat(notes): Agent System Notes upgrade'" -ForegroundColor White
}

# ================================================================== done =
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " MammothOS Notes Upgrade Complete!" -ForegroundColor Green
Write-Host "'" -ForegroundColor White
}

# ================================================================== done =
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " MammothOS Notes Upgrade Complete!" -ForegroundColor Green
Write-Host " Files written : $written"           -ForegroundColor White
Write-Host " Restart dev server to see changes."  -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
