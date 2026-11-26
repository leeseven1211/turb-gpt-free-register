//! 刷新输出的设备画像可供 Python 复用，不能混入另一套操作系统身份。
use sentinel_rs::fingerprint::DeviceFingerprint;

#[test]
fn refresh_profile_keeps_actual_device_identity() {
    let device = DeviceFingerprint::generate(Some("daily-sync-profile-fixture"));
    let profile = device.python_profile();
    assert_eq!(profile["user_agent"], device.user_agent);
    assert_eq!(profile["impersonate"], device.impersonate);
    assert_eq!(profile["sec_ch_ua_platform"], device.sec_ch_ua_platform);
    assert_eq!(profile["screen_width"], device.screen_width);
    assert_eq!(profile["screen_height"], device.screen_height);
    assert_eq!(profile["browser_os"], "Windows");
    assert!(profile["user_agent"].as_str().unwrap().contains("Windows NT"));
    assert_eq!(profile["navigator_platform"], "Win32");
    assert!(profile.get("cookies").is_none());
    assert!(profile.get("proxy").is_none());
}
