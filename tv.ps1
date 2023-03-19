#!/usr/bin/env pwsh

Import-Module -Name PowerHTML

$iwr = Get-Content -Path 'tv.html' -Raw
$iwr = $iwr -replace "`t", '' -Replace "`n", ' ' -Replace "`r", ''
$iwr = $iwr -replace '    ', ' '
$iwr = $iwr -replace '  ', ' '

$xml = $iwr | ConvertFrom-Html

$tvs = $xml.SelectNodes('//table/tbody/tr')

$js = @(); $n = 1
foreach ($tv in $tvs) {
    $trakt = $tv.ChildNodes[0].ChildNodes[0].Attributes[0].value
    $trakt_id = $trakt -split '/' | Select-Object -Last 1
    $trakt_type = $trakt -split '/' | Select-Object -Last 2 | Select-Object -First 1

    Try {
        # Split MAL by br
        $malBr = $tv.ChildNodes[1]
        # the hashtable above has 3 nodes each with a single br:
        # #text = Contains season number
        # a = Contains MAL link and title
        # br = skip

        # count how much nodes there are
        $malBrCount = $malBr.ChildNodes.Count

        # Loop through each node, on 1st, grab the season number, on 2nd, grab the MAL link and title, on 3rd, skip
        for ($i = 0; $i -lt $malBrCount; $i += 3) {
            if (($malBr.ChildNodes[$i].Name -ne 'br') -or ($malBr.ChildNodes[$i].Name -ne 'a')) {
                # Get the season number
                $season = $malBr.ChildNodes[$i].InnerText
                # Get the MAL link and title
                $mal = $malBr.ChildNodes[$i + 1].Attributes[1].value
                $mal_id = $mal -split '/' | Select-Object -Last 1
                $title = $malBr.ChildNodes[$i + 1].ChildNodes[0].InnerText
                # Write the movie to the database
                Write-Host "`e[2K`r[$n/$($tvs.Count)] Adding $title" -NoNewline
                $js += [PSCustomObject][Ordered]@{
                    title = $title
                    mal_id = [int]$mal_id
                    trakt_id = [int]$trakt_id
                    type = $trakt_type
                    season = [int]$season.Replace("S", "").Trim()
                }
            }
            else {
                Write-Error "Something went wrong with $title"
            }
        }
    }
    Catch {
        Write-Host "`r[$n/$($tvs.Count)] Skipping $title"
    }
    $n++
}

# Write the JSON to the file
$js | ConvertTo-Json -Depth 10 | Out-File -FilePath '.\db\tv.json' -Encoding UTF8 -Force
