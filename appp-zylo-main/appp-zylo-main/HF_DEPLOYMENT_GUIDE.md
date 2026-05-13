# Hugging Face Deployment Guide

Follow these steps to deploy your Dyslexia Reading Assistant to Hugging Face Cloud.

## 1. Backend Deployment (Docker Space)

1.  Log in to [Hugging Face](https://huggingface.co/).
2.  Click **New** -> **Space**.
3.  Name your space (e.g., `dyslexia-api`).
4.  Select **Docker** as the SDK.
5.  Select **Blank** (or any template) and click **Create Space**.
6.  Go to the **Files and versions** tab and upload everything from your `BACKEND` folder.
    -   *Note: Ensure `Dockerfile`, `app.py`, and `requirements.txt` are at the root of the Space.*
7.  Go to **Settings** -> **Variables and secrets**.
8.  Add a **Secret** named `MONGO_URI` with your MongoDB Atlas connection string.
9.  Add a **Secret** named `JWT_SECRET_KEY` with a random string.
10. Your API will be live at `https://your-username-your-space-name.hf.space`.

## 2. Web Frontend Deployment (Static Space)

1.  In your local `FRONTEND` folder, run:
    ```bash
    npm run build
    ```
2.  Create a **New Space** on Hugging Face.
3.  Name it (e.g., `dyslexia-app`).
4.  Select **Static** as the SDK.
5.  Go to the **Files and versions** tab and upload the contents of the `build` folder (not the folder itself, just its files).
6.  Your app will be live at `https://your-username-your-app-name.hf.space`.

## 3. Connecting the Frontend to the Backend

If you want the web app to talk to the HF backend, you should build it with the backend URL:
```bash
# Example for Windows PowerShell
$env:REACT_APP_API_URL="https://your-username-your-api-name.hf.space"; npm run build
```

## 4. Mobile App (APK)

1.  Build your APK using Expo:
    ```bash
    eas build -p android --profile preview
    ```
2.  Download the `.apk` file.
3.  Upload it to a Hugging Face **Dataset** or **Model** repository.
4.  Share the link with your users!

> [!IMPORTANT]
> Remember to update the `API_BASE_URL` in your Mobile app's code to point to the Hugging Face Space URL before building the APK.
