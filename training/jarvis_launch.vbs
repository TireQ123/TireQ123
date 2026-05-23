' J.A.R.V.I.S. — cichy launcher GUI (bez okna konsoli)
' Uruchamia serwer Ollama (jeśli trzeba) i otwiera interfejs graficzny.
' Wywoływany przez skrót na pulpicie utworzony skryptem utworz_skrot.py.

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Folder tego skryptu = ...\training ; repo = jego katalog nadrzędny
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoDir = fso.GetParentFolderName(scriptDir)

' Uruchom serwer Ollama w tle, jeśli nie odpowiada (curl zwraca błąd → start)
shell.Run "cmd /c curl -s http://localhost:11434/api/tags >nul 2>&1 || start /b ollama serve", 0, True

' Krótka pauza na rozruch serwera
WScript.Sleep 1500

' Uruchom GUI bez okna konsoli (pythonw)
shell.CurrentDirectory = repoDir
shell.Run "pythonw """ & scriptDir & "\jarvis_gui.py""", 0, False
