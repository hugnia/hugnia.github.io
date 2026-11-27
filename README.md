# Agnia's research portfolio

Open `index.html` in a browser for a local preview. The page includes a checked-in publication list, so the preview works without a server or a live API request.

## Publish and refresh

Push this project to the public `hugnia.github.io` repository. In **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**, then run **Update and publish research portfolio** from the Actions tab to import the latest publications and publish. The scheduled refresh runs once a week on Mondays at 08:24 UTC. You can also run it manually from the Actions tab. Pushes to the default branch publish site edits using the most recent saved publication list.

The workflow imports arXiv preprints and published records from Agnia's OpenAlex author profile. It also checks the public Google Scholar profile when available. It merges the results with the checked-in catalogue and the most recent publication snapshot, then uploads the updated site to GitHub Pages. If arXiv or OpenAlex is temporarily unavailable, the workflow fails and the previous Pages deployment stays live.

The **Selected work** carousel uses the six research contributions from the CV. Edit those cards in `index.html` to change which studies are featured.

## Add a write-up or video

Edit the study in `data/publications.json`. The `writeups` and `videos` arrays use entries like `{"label": "Watch on LinkedIn", "url": "https://…"}`. Add a study with its title, year, and DOI or arXiv link if it has yet to appear in this file. The workflow checks the Kairos article sitemap and Agnia's JetBrains author archive. It associates write-ups by matching titles or when a write-up links to exactly one study in the catalogue. Add other write-ups to the catalogue directly.

LinkedIn posts are added via their public share links. The site uses no LinkedIn account credentials or personal-post feed.

After editing the catalogue, run `python3 scripts/update_publications.py --offline` to refresh the local preview. Run the same command without `--offline` to check the live sources locally.
