# SD Card Layout

Format the SD card as FAT32 and copy your Spotify UI assets into this layout:

```text
/icons/
  close.png
  keyboard.png
  keyboard_0space.png
  keyboard_1.'.png
  keyboard_2abc.png
  keyboard_3def.png
  keyboard_4ghi.png
  keyboard_5jkl.png
  keyboard_6mno.png
  keyboard_7pqrs.png
  keyboard_8tuv.png
  keyboard_9wxyz.png
  liked.png
  like.png
  light_off.png
  light_on.png
  left_arrow.png
  next.png
  pause.png
  play.png
  playlists.png
  previous.png
  repeat_off.png
  repeat_on.png
  repeat_on_1.png
  right_arrow.png
  search.png
  shuffle_off.png
  shuffle_on.png
  speaker.png
  volume_down.png
  volume_up.png
icon.png
```

The app also checks `/sd/applications/spotify` before `/sd`, so advanced users can keep the same files under:

```text
/applications/spotify/
  icon.png
  icons/
```
