from importlib import reload
import gps_time_sync_vk172


def test_main_prints_message(capsys):
    reload(gps_time_sync_vk172)
    gps_time_sync_vk172.main()
    captured = capsys.readouterr()
    assert "gps_time_sync_vk172 package loaded" in captured.out
