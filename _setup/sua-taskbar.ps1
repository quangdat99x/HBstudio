# Creates the Tool Manager shortcuts and repairs the taskbar pin.
# A pin made from the running window points at bare pythonw.exe, which opens nothing.
# -LocalOnly writes only C:\Tool\Tool Manager.lnk (used for testing inside the Claude sandbox).
param([switch]$LocalOnly)

$ErrorActionPreference = 'Stop'

$ToolDir = Split-Path -Parent $PSScriptRoot
$Pythonw = 'C:\Python314\pythonw.exe'
$Script  = Join-Path $ToolDir 'run.pyw'
$Icon    = Join-Path $ToolDir 'toolmanager.ico'
$AppId   = 'VideoTools.ToolManager'   # must match APP_ID in run.pyw

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class LnkAppId {
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        void GetCount(out uint c);
        void GetAt(uint i, out PropertyKey k);
        void GetValue(ref PropertyKey k, out PropVariant v);
        void SetValue(ref PropertyKey k, ref PropVariant v);
        void Commit();
    }
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PropertyKey { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Explicit, Size = 24)]
    struct PropVariant {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr ptr;
    }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr ctx, int flags,
        [MarshalAs(UnmanagedType.LPStruct)] Guid iid, out IPropertyStore store);

    static PropertyKey Key() {
        PropertyKey k;
        k.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
        k.pid = 5;   // System.AppUserModel.ID
        return k;
    }
    static readonly Guid Iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");

    public static void Set(string path, string id) {
        IPropertyStore s;
        SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 2 /* GPS_READWRITE */, Iid, out s);
        PropertyKey k = Key();
        PropVariant v = new PropVariant();
        v.vt = 31;   // VT_LPWSTR
        v.ptr = Marshal.StringToCoTaskMemUni(id);
        s.SetValue(ref k, ref v);
        s.Commit();
        Marshal.FreeCoTaskMem(v.ptr);
        Marshal.ReleaseComObject(s);
    }
    public static string Get(string path) {
        IPropertyStore s;
        SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 0, Iid, out s);
        PropertyKey k = Key();
        PropVariant v;
        s.GetValue(ref k, out v);
        string r = v.vt == 31 ? Marshal.PtrToStringUni(v.ptr) : null;
        Marshal.ReleaseComObject(s);
        return r;
    }
}
'@

function Write-ToolShortcut($Path) {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($Path)
    $s.TargetPath = $Pythonw
    $s.Arguments = '"' + $Script + '"'
    $s.WorkingDirectory = $ToolDir
    $s.IconLocation = "$Icon,0"
    $s.Description = 'Tool Manager'
    $s.Save()
    [LnkAppId]::Set($Path, $AppId)
    if ([LnkAppId]::Get($Path) -ne $AppId) { throw "AppUserModelID was not saved: $Path" }
    Write-Host "  OK  $Path"
}

Write-ToolShortcut (Join-Path $ToolDir 'Tool Manager.lnk')
if ($LocalOnly) { return }

# Start-menu entry: Windows uses it to resolve future pins made from the running window.
Write-ToolShortcut (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Tool Manager.lnk')

# Repair the existing pin in place, only if it really is the bare Python one.
$Pin = Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\Python.lnk'
if (Test-Path $Pin) {
    $cur = (New-Object -ComObject WScript.Shell).CreateShortcut($Pin)
    if ($cur.TargetPath -ieq $Pythonw -and -not $cur.Arguments) {
        Write-ToolShortcut $Pin
    } else {
        Write-Host "  --  Python.lnk has its own target, left alone: $($cur.TargetPath) $($cur.Arguments)"
    }
} else {
    Write-Host '  --  No Python.lnk pin found. Pin "Tool Manager" from the Start menu instead.'
}

# Explorer caches taskbar icons until it restarts.
Write-Host '  Restarting Explorer to refresh the icon...'
& ie4uinit.exe -show
Stop-Process -Name explorer -Force
Start-Sleep -Seconds 2
if (-not (Get-Process explorer -ErrorAction SilentlyContinue)) { Start-Process explorer.exe }
