#include <cstdint>
#include <cstring>
#include "third_party/libretro/libretro.h"

// Callbacks provided by the frontend (RetroArch)
static retro_environment_t env_cb = nullptr;
static retro_video_refresh_t video_cb = nullptr;
static retro_audio_sample_t audio_cb = nullptr;
static retro_audio_sample_batch_t audio_batch_cb = nullptr;
static retro_input_poll_t input_poll_cb = nullptr;
static retro_input_state_t input_state_cb = nullptr;

// Minimal video buffer (test pattern)
static constexpr unsigned W = 320, H = 240;
static uint32_t fb[W * H];

extern "C" {

unsigned retro_api_version() { return RETRO_API_VERSION; }

void retro_set_environment(retro_environment_t cb) { env_cb = cb; }
void retro_set_video_refresh(retro_video_refresh_t cb) { video_cb = cb; }
void retro_set_audio_sample(retro_audio_sample_t cb) { audio_cb = cb; }
void retro_set_audio_sample_batch(retro_audio_sample_batch_t cb) { audio_batch_cb = cb; }
void retro_set_input_poll(retro_input_poll_t cb) { input_poll_cb = cb; }
void retro_set_input_state(retro_input_state_t cb) { input_state_cb = cb; }

void retro_get_system_info(retro_system_info* info) {
  std::memset(info, 0, sizeof(*info));
  info->library_name = "Axiom";
  info->library_version = "0.1.0";
  info->valid_extensions = "bin|rom";
  info->need_fullpath = false;
  info->block_extract = false;
}

void retro_get_system_av_info(retro_system_av_info* info) {
  std::memset(info, 0, sizeof(*info));
  info->timing.fps = 60.0;
  info->timing.sample_rate = 48000.0;
  info->geometry.base_width = W;
  info->geometry.base_height = H;
  info->geometry.max_width = W;
  info->geometry.max_height = H;
  info->geometry.aspect_ratio = float(W) / float(H);
}

void retro_init() {
  // Tell frontend we output XRGB8888 frames
  retro_pixel_format fmt = RETRO_PIXEL_FORMAT_XRGB8888;
  if (env_cb) env_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &fmt);
  std::memset(fb, 0, sizeof(fb));
}

void retro_deinit() {}
void retro_reset() { std::memset(fb, 0, sizeof(fb)); }

bool retro_load_game(const retro_game_info* game) {
  (void)game;
  return true;
}
void retro_unload_game() {}
unsigned retro_get_region() { return RETRO_REGION_NTSC; }

void retro_run() {
  if (input_poll_cb) input_poll_cb();

  // test pattern
  static uint32_t t = 0; t++;
  for (unsigned y = 0; y < H; y++)
    for (unsigned x = 0; x < W; x++) {
      uint8_t r = uint8_t((x + t) & 0xFF);
      uint8_t g = uint8_t((y + t) & 0xFF);
      uint8_t b = uint8_t((x + y + t) & 0xFF);
      fb[y * W + x] = (0xFFu << 24) | (uint32_t(r) << 16) | (uint32_t(g) << 8) | b;
    }

  if (video_cb) video_cb(fb, W, H, W * sizeof(uint32_t));
}

// Savestate stubs for now
size_t retro_serialize_size() { return 0; }
bool retro_serialize(void*, size_t) { return false; }
bool retro_unserialize(const void*, size_t) { return false; }

void retro_cheat_reset() {}
void retro_cheat_set(unsigned, bool, const char*) {}

void* retro_get_memory_data(unsigned) { return nullptr; }
size_t retro_get_memory_size(unsigned) { return 0; }

} // extern "C"
