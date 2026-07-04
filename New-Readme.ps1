<#
.SYNOPSIS
  Interactive README.md generator — 2026 best practices.
  Produces a capsule-render header/footer, badge table, Quick Start,
  FAQ, and "See Also" section. Paste the output or pipe to a file.

.EXAMPLE
  .\New-Readme.ps1
  .\New-Readme.ps1 -OutputPath .\README.md
#>

param(
  [string]$OutputPath
)

function Read-Prompt($label, $default) {
  $d = if ($default) { " [$default]" } else { "" }
  $v = Read-Host "${label}${d}"
  if ([string]::IsNullOrWhiteSpace($v)) { $default } else { $v }
}

Clear-Host
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    README.md Generator — 2026        ║" -ForegroundColor Cyan
Write-Host "║    Leave blank to use [default]      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Basic Info ──────────────────────────────────
$projectName  = Read-Prompt "Project name" "MyProject"
$tagline      = Read-Prompt "One-line tagline" "A cool project built at WHU"
$overview     = Read-Prompt "Overview (1-2 sentences)" "A brief description of what this project does."
$why          = Read-Prompt "Why this project? (motivation)" "Fills a specific gap in X"

# ── Tech Stack ──────────────────────────────────
$stack = @()
Write-Host "`n── Tech Stack (enter empty line to finish) ──" -ForegroundColor Yellow
while ($true) {
  $cat = Read-Host "  Category (e.g. Language, Framework)"
  if ([string]::IsNullOrWhiteSpace($cat)) { break }
  $tech = Read-Host "  Technologies (e.g. Python 3.10, PyTorch)"
  $stack += @{ Category = $cat; Tech = $tech }
}
if ($stack.Count -eq 0) {
  $stack += @{ Category = "Language"; Tech = "Python 3" }
}

# ── Quick Start ─────────────────────────────────
$install   = Read-Prompt "Install command" "pip install -r requirements.txt"
$runCmd    = Read-Prompt "Run command" "python main.py"
$features  = @()
Write-Host "`n── Features (enter empty line to finish) ──" -ForegroundColor Yellow
while ($true) {
  $f = Read-Host "  Feature name"
  if ([string]::IsNullOrWhiteSpace($f)) { break }
  $d = Read-Host "  Description"
  $features += @{ Name = $f; Desc = $d }
}
if ($features.Count -eq 0) {
  $features += @{ Name = "Core feature"; Desc = "What it does" }
}

# ── FAQ ─────────────────────────────────────────
$faq = @()
Write-Host "`n── FAQ (enter empty line to finish) ──" -ForegroundColor Yellow
while ($true) {
  $q = Read-Host "  Question"
  if ([string]::IsNullOrWhiteSpace($q)) { break }
  $a = Read-Host "  Answer"
  $faq += @{ Q = $q; A = $a }
}

# ── Context ─────────────────────────────────────
$course       = Read-Prompt "Course name (or 'Research' / 'OSS')" "Course Name"
$seeAlsoText  = ""
$addSeeAlso   = Read-Prompt "Add 'See Also' links? (y/n)" "n"
if ($addSeeAlso -eq "y") {
  $s1Name = Read-Prompt "  Related project 1 name" ""
  $s1Url  = Read-Prompt "  Related project 1 URL" ""
  $s1Why  = Read-Prompt "  Why related" ""
  $s2Name = Read-Prompt "  Related project 2 name" ""
  $s2Url  = Read-Prompt "  Related project 2 URL" ""
  $s2Why  = Read-Prompt "  Why related" ""
  $seeAlsoText = "`n## 🔗 See Also`n`n"
  if ($s1Name) { $seeAlsoText += "- [$s1Name]($s1Url) — $s1Why`n" }
  if ($s2Name) { $seeAlsoText += "- [$s2Name]($s2Url) — $s2Why`n" }
}

# ── Gradient colors ─────────────────────────────
$grad1 = Read-Prompt "Gradient start hex (e.g. 667eea)" "667eea"
$grad2 = Read-Prompt "Gradient end hex   (e.g. 764ba2)" "764ba2"

# ── Build README ────────────────────────────────
$badgeRows = ""
foreach ($b in $stack) {
  $badgeRows += "| **$($b.Category)** | $($b.Tech) |`n"
}

$featureRows = ""
foreach ($f in $features) {
  $featureRows += "- **$($f.Name)**: $($f.Desc)`n"
}

$faqRows = ""
foreach ($item in $faq) {
  $faqRows += "| **$($item.Q)** | $($item.A) |`n"
}
if ([string]::IsNullOrWhiteSpace($faqRows)) {
  $faqRows = "| _Add your questions here_ | _Answers_ |`n"
}

$output = @"
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:${grad1},100:${grad2}&height=180&section=header&text=${projectName}&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=${tagline}&descAlignY=55&descAlign=50" width="100%" />
</p>

| Category | Stack |
|----------|-------|
${badgeRows}## 📋 Overview

${overview}

> **Why ${projectName}?** ${why}

## 🚀 Quick Start

### Prerequisites

```bash
${install}
```

### Run

```bash
${runCmd}
```

## ✨ Key Features

${featureRows}## 🏗️ Architecture

```
${projectName}/
├── src/                    # Source code
├── tests/                  # Test suite
├── docs/                   # Documentation
└── README.md               # This file
```

## ❓ FAQ

| Question | Answer |
|----------|--------|
${faqRows}${seeAlsoText}
## 🎓 Academic Context

This project was completed as part of **${course}** at **Wuhan University**, School of Computer Science.

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:${grad2},100:${grad1}&height=100&section=footer" width="100%" />
</p>
"@

# ── Output ──────────────────────────────────────
if ($OutputPath) {
  $output | Out-File -FilePath $OutputPath -Encoding utf8
  Write-Host "`n✅ README written to: $OutputPath" -ForegroundColor Green
} else {
  Write-Host "`n" + "="*50 -ForegroundColor Cyan
  Write-Host "GENERATED README.md (copy this)" -ForegroundColor Cyan
  Write-Host "="*50 -ForegroundColor Cyan
  $output
}

Write-Host "`nTip: Preview gradients at https://capsule-render.vercel.app/" -ForegroundColor DarkGray
