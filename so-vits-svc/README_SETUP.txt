# Setup Instructions

1. **Download Pre-trained Models**
   Due to network issues, the automatic download failed. Please download the following files manually and place them in the correct folders:

   * **pretrain/checkpoint_best_legacy_500.pt**
     * Link: https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt
     * Rename the downloaded file `hubert_base.pt` to `checkpoint_best_legacy_500.pt`.
     * Place it in the `pretrain` folder.

   * **logs/44k/G_0.pth**
     * Link: https://huggingface.co/Gaiigd/so-vits-svc-4.0-init/resolve/main/G_0.pth
     * Place it in `logs/44k` folder.

   * **logs/44k/D_0.pth**
     * Link: https://huggingface.co/Gaiigd/so-vits-svc-4.0-init/resolve/main/D_0.pth
     * Place it in `logs/44k` folder.

2. **Run Feature Extraction**
   After placing the models, run this command in the terminal:
   ```bash
   python preprocess_hubert_f0.py
   ```

3. **Start Training**
   Once feature extraction is done, start training:
   ```bash
   python train.py -c configs/config.json -m 44k
   ```

4. **Inference (Usage)**
   After training for a while (e.g., 10000 steps), you can use the model to convert voice:
   ```bash
   python inference_main.py -m "logs/44k/G_10000.pth" -c "configs/config.json" -n "input_audio.wav" -t 0 -s "my_voice"
   ```
   (Replace `G_10000.pth` with your latest checkpoint).

## Note
Your audio file `Voice (251027.2351).mp3` has been processed and sliced into `dataset_raw/my_voice`.
Dependencies are installed.
Config files are generated.
