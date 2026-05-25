# Environment Setup

Run these commands from the project root (`FL_Drug_Discovery`) in **PowerShell** on Windows.

## 1. Create a virtual environment

```powershell
python -m venv venv
```

## 2. Activate the virtual environment

```powershell
.\venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy, run once (current user only):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

## 4. Download the dataset

With the virtual environment still active:

```powershell
python download_data.py
```

The file `ChG-TargetDecagon_targets.csv.gz` will be saved under `data/`.
