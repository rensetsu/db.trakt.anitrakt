#!/usr/bin/env pwsh

# Import-Module -Name PowerHTML

Invoke-WebRequest -Uri "https://anitrakt.huere.net/db/db_index_movies.php" -UseBasicParsing -OutFile 'movies.html'

Invoke-WebRequest -Uri "https://anitrakt.huere.net/db/db_index_shows.php" -UseBasicParsing -OutFile 'tv.html'

.\movies.ps1

.\tv.ps1