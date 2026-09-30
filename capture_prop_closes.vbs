' P61: start capture_prop_closes.cmd with no console window (window style 0) and
' pass its exit code back to Task Scheduler. A visible console in the user's
' session can be closed or sent Ctrl+C, which kills the run (0xC000013A, 9/30 17:30).
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
rc = CreateObject("WScript.Shell").Run("cmd.exe /c """ & here & "\capture_prop_closes.cmd""", 0, True)
WScript.Quit rc
