# Printer Service Logger (Tkinter + SQLite)

A simple desktop app to track printers and their service notes. Built with Python's Tkinter and SQLite (no external dependencies).

## Features
- Create, view, edit, and delete printers
  - Fields: Printer ID, Name, Manufacturer, Model, Hours
- Add, edit, and delete service notes/tasks for each printer
- Notes auto-stamp the created date
- All data stored locally in `printer_service.db`

## Requirements
- Python 3.8+
- Windows, macOS, or Linux

## Run
From the project folder:

```bash
python app.py
```

On Windows PowerShell, you may need:

```powershell
py app.py
```

## Usage
- Left list shows all printers. Use Add/Edit/Delete/Refresh buttons.
- Right pane has a form to add a new printer or update the selected one.
  - "Save As New" creates a new printer from the form.
  - "Update Selected" updates the highlighted printer.
  - Hours must be an integer (blank becomes 0).
- Service Logs section manages notes for the selected printer.
  - Add, Edit, Delete notes; each note records the current timestamp.

## Data
- Database file: `printer_service.db` in the project directory
- Foreign keys enabled; deleting a printer removes its notes

## Backup
- Close the app, then copy `printer_service.db` to back up.

## Troubleshooting
- If the window does not appear, ensure Python Tkinter is available:
  - Windows Store Python includes Tk by default.
  - Linux may require `python3-tk` (or similar) via your package manager.
