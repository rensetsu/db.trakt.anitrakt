#!/usr/bin/env pwsh

Import-Module -Name PowerHTML

# $iwr = Invoke-WebRequest -Uri $uri -UseBasicParsing -OutFile 'movies.html'
$iwr = Get-Content -Path 'index.html' -Raw
$iwr = $iwr -replace "`t", '' -Replace "`n", ' ' -Replace "`r", ''
$iwr = $iwr -replace '  ', ' '

$xml = $iwr | ConvertFrom-Html

$movies = $xml.SelectNodes('//table/tbody/tr')

# Assume the layout as such:
<#
<tbody>
    <tr>
        <td id=trakt><a href=http://trakt.tv/movies/767993 target=_blank>"Please Describe Yourself in One Word":
                I'm Bad at the Question.</a></td>
        <td><a target=_blank href=https://myanimelist.net/anime/50762>Anata wo Hitokoto de Arawashite Kudasai:
                no Shitsumon ga Nigate da.</a></td>
    </tr>
</tbody>
#>
# Do loop for each movie in tr
$js = @(); $n = 1
ForEach ($mv in $movies) {
    # Get the trakt link
    $trakt = $mv.ChildNodes[1].ChildNodes[0].Attributes[0].value
    Try {
        # Get the MAL link
        $mal = $mv.ChildNodes[3].ChildNodes[0].Attributes[1].value
        # Get the title
        $title = $mv.SelectSingleNode('td[1]/a').InnerText
        # Get the MAL ID
        $mal_id = $mal -split '/' | Select-Object -Last 1
        # Get the trakt ID
        $trakt_id = $trakt -split '/' | Select-Object -Last 1
        $trakt_type = $trakt -split '/' | Select-Object -Last 2 | Select-Object -First 1

        # Write the movie to the database
        Write-Host "`r[$n/$($movies.Count)] Adding $title to the database" -NoNewline
        $js += [PSCustomObject][Ordered]@{
            title = $title
            mal_id = $mal_id
            trakt_id = $trakt_id
            type = $trakt_type
        }
    }
    Catch {
        Write-Host "`r[$n/$($movies.Count)] Skipping $title"
    }
    $n++
}

# Write the JSON to the file
$js | ConvertTo-Json -Depth 10 | Out-File -FilePath '.\db\movies.json' -Encoding UTF8 -Force