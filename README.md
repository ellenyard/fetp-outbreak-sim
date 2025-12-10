# FETP Outbreak Investigation Simulation - DEMO

Interactive outbreak investigation training for Field Epidemiology Training Programs.

## Quick Start for Demo Tomorrow

### Step 1: Set Up Streamlit Cloud Account

1. Go to https://share.streamlit.io/
2. Sign up with your email (use your work email)
3. Connect your GitHub account when prompted

### Step 2: Upload to GitHub

1. Go to https://github.com/
2. Click "New Repository" (green button)
3. Name it: `fetp-outbreak-sim`
4. Make it **Public** (required for free Streamlit hosting)
5. Click "Create Repository"

6. Upload these files:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   
   (You can drag and drop files right in GitHub web interface)

### Step 3: Deploy to Streamlit Cloud

1. Go back to https://share.streamlit.io/
2. Click "New app"
3. Select your repository: `fetp-outbreak-sim`
4. Main file path: `app.py`
5. Click "Deploy"

### Step 4: Add Your API Key (CRITICAL!)

1. While the app is deploying, click "Advanced settings" or "Secrets"
2. In the secrets editor, add:

```toml
ANTHROPIC_API_KEY = "sk-ant-api-YOUR-KEY-HERE"
```

(Replace `sk-ant-api-YOUR-KEY-HERE` with your actual API key from console.anthropic.com)

3. Click "Save"

### Step 5: Get Your Demo URL

Once deployed (takes 2-3 minutes), you'll get a URL like:
`https://fetp-outbreak-sim.streamlit.app`

**Share this URL with your team tomorrow!**

---

## Testing Before Your Demo

1. Open the URL yourself
2. Try the map view
3. Interview Dr. Mensah:
   - Ask: "Can you tell me about the outbreak?"
   - Ask: "What are the main symptoms?"
   - Ask something unexpected like: "Has anyone died?"
4. Interview Mrs. Abena
5. Check that responses are natural and contextual

---

## Demo Flow (10-15 minutes)

**Minutes 0-2: Introduction**
- Share URL with team
- Everyone opens on their device
- Brief context: "Interactive outbreak investigation training"

**Minutes 2-5: Interface Tour**
- Show the map (cases clustered around Well #1)
- Show contacts panel
- Explain multi-day structure

**Minutes 5-10: Live Interview (The "WOW" moment)**
- Interview Dr. Mensah together
- Ask 2-3 scripted questions
- Then ask something unexpected to show AI flexibility
- Maybe have someone from audience suggest a question
- Interview another character if time allows

**Minutes 10-15: Discussion**
- Show how this would expand to full 5-day investigation
- Discuss budget, feasibility
- Q&A

---

## Troubleshooting

**If the app won't load:**
- Check that your API key is correct in Secrets
- Make sure the key starts with `sk-ant-api`
- Try restarting the app (three dots menu → Reboot)

**If interviews aren't working:**
- Check browser console for errors (F12)
- Verify API key is active on console.anthropic.com
- Make sure you have credits ($5 free credit should be plenty)

**If deployment fails:**
- Make sure requirements.txt is in the repository
- Check that files are named exactly: `app.py` (lowercase, no spaces)

---

## Cost Estimate

For a 15-minute demo with 10 people:
- ~30-50 API calls total
- Each call: ~500 tokens average
- Cost: **Less than $0.50 total**

Your $5 free credit will last through many demos!

---

## After the Demo

If your team loves it (they will!), next steps:
1. Expand to full Day 1 scenario
2. Add Days 2-5 functionality
3. Create multiple outbreak scenarios
4. Eventually migrate to CDC infrastructure (Posit Connect)

---

## Support

If you run into issues:
- Email support from the Streamlit Cloud dashboard
- Check Anthropic API status: status.anthropic.com
- Streamlit docs: docs.streamlit.io

---

## Demo Scenario Details

**Outbreak:** Cholera in Riverside Village
**Cases:** 15 confirmed, 3 deaths
**Key Finding:** All cases use contaminated Well #1
**Learning Objective:** Recognize waterborne outbreak patterns

**Characters:**
- 👨‍⚕️ Dr. Mensah (District Health Officer) - Medical overview
- 👩‍⚕️ Mrs. Abena (Community Health Worker) - Local knowledge
- 👴 Chief Okoye (Village Chief) - Infrastructure info
- 🚰 Mohammed (Water Vendor) - Environmental observations

Each character has unique knowledge that trainees must discover through questioning!

---

Good luck with your demo! 🚀
