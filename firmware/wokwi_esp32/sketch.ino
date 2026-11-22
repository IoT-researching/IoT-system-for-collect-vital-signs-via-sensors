#include <Arduino.h>
#include <math.h>

// ===== Cấu hình ca kiểm thử =====
const int FS = 100;                 // 100 mẫu/giây
const int DURATION_SECONDS = 4;
const int N = FS * DURATION_SECONDS; // 400 mẫu

const float TARGET_HR = 75.0;       // Thử lần lượt 60, 75, 90
const float NOISE_LEVEL = 0.0;      // Thử 0 hoặc 250
const bool NO_FINGER = true;       // true = mô phỏng không có ngón tay

uint32_t redData[N];
uint32_t irData[N];

void generateSignal() {
  const float pi = 3.14159265;
  const float frequency = TARGET_HR / 60.0;

  for (int i = 0; i < N; i++) {
    float t = (float)i / FS;

    if (NO_FINGER) {
      // Mức nền thấp, không có tín hiệu mạch rõ ràng
      redData[i] = (uint32_t)(4500 + random(-100, 101));
      irData[i]  = (uint32_t)(5000 + random(-100, 101));
    } else {
      float pulse =
        sin(2 * pi * frequency * t) +
        0.3 * sin(4 * pi * frequency * t);

      float red = 95000 + 600 * pulse;
      float ir  = 100000 + 1500 * pulse;

      if (NOISE_LEVEL > 0) {
        float noiseRed = random(-1000, 1001) / 1000.0 * NOISE_LEVEL;
        float noiseIR  = random(-1000, 1001) / 1000.0 * NOISE_LEVEL;
        red += noiseRed;
        ir  += noiseIR;
      }

      redData[i] = (uint32_t)red;
      irData[i]  = (uint32_t)ir;
    }

    delay(1000 / FS); // mô phỏng lấy mẫu 100 Hz
  }
}

void printArray(const char* name, uint32_t data[], int length) {
  Serial.printf("\"%s\":[", name);

  for (int i = 0; i < length; i++) {
    Serial.print(data[i]);

    if (i < length - 1) {
      Serial.print(",");
    }
  }

  Serial.print("]");
}

void printJson() {
  Serial.print("{\"case\":\"");

  if (NO_FINGER) {
    Serial.print("No Finger");
  } else if (NOISE_LEVEL > 0) {
    Serial.print("Noisy ");
    Serial.print(TARGET_HR, 0);
    Serial.print(" bpm");
  } else {
    Serial.print("Clean ");
    Serial.print(TARGET_HR, 0);
    Serial.print(" bpm");
  }

  Serial.print("\",\"fs\":");
  Serial.print(FS);
  Serial.print(",");

  printArray("red", redData, N);
  Serial.print(",");
  printArray("ir", irData, N);

  Serial.println("}");
}

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0));

  Serial.println("TV2 ESP32 PPG simulator started");
  generateSignal();

  Serial.println("JSON_BEGIN");
  printJson();
  Serial.println("JSON_END");
}

void loop() {
  // Chỉ tạo và gửi một cửa sổ mẫu trong lần chạy này.
}
