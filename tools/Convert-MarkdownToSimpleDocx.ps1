param(
    [Parameter(Mandatory = $true)] [string] $InputPath,
    [Parameter(Mandatory = $true)] [string] $TemplatePath,
    [Parameter(Mandatory = $true)] [string] $OutputPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Escape-Xml([string] $Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

function New-ParagraphXml([string] $Text, [string] $Style = '') {
    $escaped = Escape-Xml $Text
    $styleXml = if ($Style) { "<w:pPr><w:pStyle w:val=`"$Style`"/></w:pPr>" } else { '' }
    return "<w:p>$styleXml<w:r><w:t xml:space=`"preserve`">$escaped</w:t></w:r></w:p>"
}

$inputFull = (Resolve-Path -LiteralPath $InputPath).Path
$templateFull = (Resolve-Path -LiteralPath $TemplatePath).Path
$outputFull = [System.IO.Path]::GetFullPath($OutputPath)
$lines = [System.IO.File]::ReadAllLines($inputFull, [System.Text.Encoding]::UTF8)

$body = New-Object System.Collections.Generic.List[string]
$inCode = $false
foreach ($rawLine in $lines) {
    $line = $rawLine.TrimEnd()
    if ($line -eq '```text' -or $line -eq '```') {
        $inCode = -not $inCode
        continue
    }
    if ($inCode) {
        $body.Add((New-ParagraphXml $line 'Code'))
    } elseif ($line -match '^# (.+)$') {
        $body.Add((New-ParagraphXml $Matches[1] 'Title'))
    } elseif ($line -match '^## (.+)$') {
        $body.Add((New-ParagraphXml $Matches[1] 'Heading1'))
    } elseif ($line -match '^### (.+)$') {
        $body.Add((New-ParagraphXml $Matches[1] 'Heading2'))
    } elseif ($line -match '^- (.+)$') {
        $body.Add((New-ParagraphXml ("• " + $Matches[1]) 'ListParagraph'))
    } elseif ($line -match '^\d+\. (.+)$') {
        $body.Add((New-ParagraphXml $line 'ListParagraph'))
    } elseif ([string]::IsNullOrWhiteSpace($line)) {
        $body.Add('<w:p/>')
    } else {
        $plain = $line -replace '\*\*', '' -replace '`', ''
        $body.Add((New-ParagraphXml $plain))
    }
}

$documentXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
    '<w:body>' + ($body -join '') +
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>' +
    '</w:body></w:document>'

[System.IO.File]::Copy($templateFull, $outputFull, $true)
$archive = [System.IO.Compression.ZipFile]::Open($outputFull, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    $oldEntry = $archive.GetEntry('word/document.xml')
    if ($null -ne $oldEntry) { $oldEntry.Delete() }
    $entry = $archive.CreateEntry('word/document.xml', [System.IO.Compression.CompressionLevel]::Optimal)
    $stream = $entry.Open()
    try {
        $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
        try { $writer.Write($documentXml) } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
} finally {
    $archive.Dispose()
}

Write-Output $outputFull
