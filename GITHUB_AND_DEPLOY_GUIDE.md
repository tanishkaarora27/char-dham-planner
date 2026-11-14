# Put the project on GitHub and host the app for free

Run every command inside the `char-dham-planner` folder. Replace `YOUR-USERNAME` with your GitHub username.

## Part 1: push to GitHub

1. Install Git from https://git-scm.com and check it works:
   ```bash
   git --version
   ```
2. Tell Git who you are (once per computer):
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
3. Turn the folder into a Git repository:
   ```bash
   git init
   ```
4. Stage every file (`.gitignore` keeps `venv/` and caches out):
   ```bash
   git add .
   ```
5. Save the first snapshot:
   ```bash
   git commit -m "Char Dham Yatra planner using A*"
   ```
6. Rename the branch to `main`, the name GitHub expects:
   ```bash
   git branch -M main
   ```
7. Create the empty repo on the website: github.com > **+** > **New repository** > name it
   `char-dham-planner` > **Public** > do NOT tick "Add a README" > **Create repository**.
8. Link your folder to that repo:
   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/char-dham-planner.git
   ```
9. Upload:
   ```bash
   git push -u origin main
   ```

**If it asks for a password:** GitHub does not accept your account password here. Create a personal
access token: github.com > your photo > **Settings** > **Developer settings** > **Personal access tokens**
> **Tokens (classic)** > **Generate new token** > tick **repo** > generate > copy it. Paste the token when
Git asks for a password (your username stays the same). Nothing appears while you paste; that is normal.

**Later changes:**
```bash
git add .
git commit -m "Describe what changed"
git push
```

**Common errors**
- `remote origin already exists`: run `git remote set-url origin https://github.com/YOUR-USERNAME/char-dham-planner.git`
- `failed to push some refs`: you ticked "Add a README" on GitHub. Run `git pull origin main --allow-unrelated-histories`, then push again.

## Part 2: deploy on Streamlit Community Cloud (free)

1. Go to https://share.streamlit.io and sign in with GitHub. Allow access to your repositories.
2. Click **Create app** > **Deploy a public app from GitHub**.
3. Fill in: Repository `YOUR-USERNAME/char-dham-planner`, Branch `main`, Main file path `app.py`.
4. Optionally choose a custom URL, then click **Deploy**. The first build takes a few minutes while it
   installs `requirements.txt`.
5. Copy the public link (it looks like `https://your-name.streamlit.app`) into slide 6 of the PPT and into
   the README.

Every `git push` to `main` redeploys the app automatically. A free app sleeps after a period without
visitors; open the link a few minutes before your demo and press the wake-up button if it shows one.
The menus on GitHub and Streamlit change from time to time, so a label may differ slightly from the above.
