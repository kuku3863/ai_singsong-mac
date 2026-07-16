import os
import logging
import traceback
logger = logging.getLogger(__name__)

import librosa,ffmpeg
import numpy as np
import soundfile as sf
import torch

# 解决 ONNX Runtime 在 Windows 上找不到 cuDNN DLL 的问题
if torch.cuda.is_available():
    torch_lib_path = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.path.exists(torch_lib_path):
        # Python 3.8+ 需要显式添加 DLL 搜索目录
        try:
            os.add_dll_directory(torch_lib_path)
        except Exception:
            pass

from tqdm import tqdm

device = 'cuda' if torch.cuda.is_available() else 'cpu'
is_half = device == 'cuda'

class ConvTDFNetTrim:
    def __init__(
        self, device, model_name, target_name, L, dim_f, dim_t, n_fft, hop=1024
    ):
        super(ConvTDFNetTrim, self).__init__()

        self.dim_f = dim_f
        self.dim_t = 2**dim_t
        self.n_fft = n_fft
        self.hop = hop
        self.n_bins = self.n_fft // 2 + 1
        self.chunk_size = hop * (self.dim_t - 1)
        self.window = torch.hann_window(window_length=self.n_fft, periodic=True).to(
            device
        )
        self.target_name = target_name
        self.blender = "blender" in model_name

        self.dim_c = 4
        out_c = self.dim_c * 4 if target_name == "*" else self.dim_c
        self.freq_pad = torch.zeros(
            [1, out_c, self.n_bins - self.dim_f, self.dim_t]
        ).to(device)

        self.n = L // 2

    def stft(self, x):
        x = x.reshape([-1, self.chunk_size])
        x = torch.stft(
            x,
            n_fft=self.n_fft,
            hop_length=self.hop,
            window=self.window,
            center=True,
            return_complex=True,
        )
        x = torch.view_as_real(x)
        x = x.permute([0, 3, 1, 2])
        x = x.reshape([-1, 2, 2, self.n_bins, self.dim_t]).reshape(
            [-1, self.dim_c, self.n_bins, self.dim_t]
        )
        return x[:, :, : self.dim_f]

    def istft(self, x, freq_pad=None):
        freq_pad = (
            self.freq_pad.repeat([x.shape[0], 1, 1, 1])
            if freq_pad is None
            else freq_pad
        )
        freq_pad = freq_pad.to(x.device)
        x = torch.cat([x, freq_pad], -2)
        c = 4 * 2 if self.target_name == "*" else 2
        x = x.reshape([-1, c, 2, self.n_bins, self.dim_t]).reshape(
            [-1, 2, self.n_bins, self.dim_t]
        )
        x = x.permute([0, 2, 3, 1])
        x = x.contiguous()
        x = torch.view_as_complex(x)
        if is_half:
            window = self.window.half().to(x.device)
        else:
            window = self.window.to(x.device)
        x = torch.istft(
            x, n_fft=self.n_fft, hop_length=self.hop, window=window, center=True
        )
        return x.reshape([-1, c, self.chunk_size])


def get_models(device, dim_f, dim_t, n_fft):
    return ConvTDFNetTrim(
        device=device,
        model_name="Conv-TDF",
        target_name="UVR_MDXNET_KARA_2",
        L=11,
        dim_f=dim_f,
        dim_t=dim_t,
        n_fft=n_fft,
    )


from scipy.io import wavfile

def save_audio_robust(path, data, sr):
    """鲁棒地保存音频文件，防止 libsndfile 维度错误或格式报错"""
    try:
        # 统一维度为 (samples, channels)
        # 如果第一维小于 10（极大概率是声道数），而第二维很大，则需要转置
        if data.ndim == 2:
            if data.shape[0] < 10 and data.shape[1] > data.shape[0]:
                data = data.T
        
        # 确保数据没有 NaN 或 Inf
        data = np.nan_to_num(data)
        # 如果是 float32，限制在 [-1, 1]
        if data.dtype == np.float32:
            data = np.clip(data, -1.0, 1.0)
        
        # 优先使用 soundfile
        sf.write(path, data, sr)
    except Exception as e:
        print(f"⚠️ Soundfile 保存失败: {e}，尝试使用 Scipy 回退")
        try:
            # Scipy 保存 16-bit PCM 更稳健
            data_int16 = (data * 32767).astype(np.int16)
            wavfile.write(path, sr, data_int16)
        except Exception as e2:
            print(f"❌ Scipy 保存也失败了: {e2}")
            # 强制再转置一次试试
            try:
                wavfile.write(path, sr, data_int16.T)
            except:
                raise e2

class Predictor:
    def __init__(self, args):
        import onnxruntime as ort

        print(f"ONNX Runtime available providers: {ort.get_available_providers()}")
        self.args = args
        self.model_ = get_models(
            device=device, dim_f=args.dim_f, dim_t=args.dim_t, n_fft=args.n_fft
        )
        if getattr(args, "force_cpu", False):
            self.model = ort.InferenceSession(
                args.onnx,
                providers=["CPUExecutionProvider"],
            )
        else:
            try:
                # 显式指定 CUDA 选项，禁用可能导致卡顿的 TensorrtExecutionProvider
                # 并且不使用默认的 provider 顺序，直接锁定 CUDA
                cuda_options = {
                    'device_id': 0,
                    'arena_extend_strategy': 'kSameAsRequested',
                    # 移除硬性显存限制，让 ONNX 自动利用可用显存
                    # 'gpu_mem_limit': 4 * 1024 * 1024 * 1024, 
                    'cudnn_conv_algo_search': 'DEFAULT',
                    'do_copy_in_default_stream': True,
                }
                self.model = ort.InferenceSession(
                    args.onnx,
                    providers=[
                        ('CUDAExecutionProvider', cuda_options),
                        'CPUExecutionProvider'
                    ],
                )
            except Exception as e:
                print(f"⚠️ GPU 会话初始化失败，回退到 CPU 模式: {e}")
                self.model = ort.InferenceSession(
                    args.onnx,
                    providers=["CPUExecutionProvider"],
                )
        if "CUDAExecutionProvider" in self.model.get_providers():
            print(f"✅ MDX-Net 正在使用 GPU 加速 (CUDA)")
        else:
            print(f"ℹ️ MDX-Net 正在使用 CPU 运行")
            
        print(f"ONNX Runtime selected provider: {self.model.get_providers()}")
        logger.info("ONNX load done")

    def demix(self, mix):
        samples = mix.shape[-1]
        margin = self.args.margin
        chunk_size = self.args.chunks * 44100
        assert not margin == 0, "margin cannot be zero!"
        if margin > chunk_size:
            margin = chunk_size

        segmented_mix = {}

        if self.args.chunks == 0 or samples < chunk_size:
            chunk_size = samples

        counter = -1
        for skip in range(0, samples, chunk_size):
            counter += 1

            s_margin = 0 if counter == 0 else margin
            end = min(skip + chunk_size + margin, samples)

            start = skip - s_margin

            segmented_mix[skip] = mix[:, start:end].copy()
            if end == samples:
                break

        sources = self.demix_base(segmented_mix, margin_size=margin)
        """
        mix:(2,big_sample)
        segmented_mix:offset->(2,small_sample)
        sources:[ (2,big_sample) ]
        """
        return [sources]

    def demix_base(self, mixes, margin_size):
        chunked_sources = []
        progress_bar = tqdm(total=len(mixes))
        progress_bar.set_description("Processing")
        
        for mix_offset in mixes:
            cmix = mixes[mix_offset]
            n_sample = cmix.shape[1]
            base_n_sample = n_sample
            model = self.model_
            trim = model.n_fft // 2
            gen_size = model.chunk_size - 2 * trim
            
            total_tar_signal = None
            shifts = int(getattr(self.args, "shifts", 1) or 1)
            
            for shift_idx in range(shifts):
                offset = int(shift_idx * (gen_size / shifts))
                if offset > 0:
                    current_mix = np.pad(
                        cmix,
                        pad_width=((0, 0), (offset, gen_size)),
                        mode="constant",
                    )
                else:
                    current_mix = cmix
                n_sample = current_mix.shape[1]
                pad = gen_size - n_sample % gen_size
                mix_p = np.concatenate(
                    (np.zeros((2, trim)), current_mix, np.zeros((2, pad)), np.zeros((2, trim))), 1
                )
                
                mix_waves = []
                i = 0
                while i < n_sample + pad:
                    waves = np.array(mix_p[:, i : i + model.chunk_size])
                    mix_waves.append(waves)
                    i += gen_size
                
                dtype = torch.float32
                # stft 预处理
                mix_waves_tensor = torch.tensor(mix_waves, dtype=dtype).to(device)
                spek = model.stft(mix_waves_tensor).cpu().numpy()
                del mix_waves_tensor, mix_waves
                
                # 将数据保持在 CPU 上，仅在推理时交给 ONNX 处理，避免频繁的 GPU/CPU 同步
                input_data = spek
                
                # 定义内部小批次大小，防止由于 Segment 太长导致的 ONNX 内部 OOM
                # 对于 4060 (8GB)，128 是一个安全且高效的 batch_size
                mini_batch_size = 64 
                num_batches = (input_data.shape[0] + mini_batch_size - 1) // mini_batch_size
                
                with torch.no_grad():
                    _ort = self.model
                    all_tar_waves = []
                    
                    for b in range(num_batches):
                        batch_start = b * mini_batch_size
                        batch_end = min((b + 1) * mini_batch_size, input_data.shape[0])
                        batch_input = input_data[batch_start:batch_end]
                        
                        # Denoise 极致优化：将正相和反相数据拼接成一个大 Batch 一次性交给 GPU 处理
                        # 这能减少一半的 ONNX 调用开销和 GPU/CPU 同步开销
                        if self.args.denoise:
                            # 拼接正反数据: [batch*2, 4, 3072, 256]
                            batch_input_combined = np.concatenate([batch_input, -batch_input], axis=0)
                            combined_pred = _ort.run(None, { "input": batch_input_combined })[0]
                            
                            # 拆分预测结果并计算均值去除残留
                            half = combined_pred.shape[0] // 2
                            pos_pred = combined_pred[:half]
                            neg_pred = combined_pred[half:]
                            spec_pred = (pos_pred - neg_pred) * 0.5
                            
                            batch_tar_waves = model.istft(torch.tensor(spec_pred, dtype=dtype).to(device))
                            del batch_input_combined, combined_pred, pos_pred, neg_pred, spec_pred
                        else:
                            batch_tar_waves = model.istft(
                                torch.tensor(_ort.run(None, { "input": batch_input })[0], dtype=dtype).to(device)
                            )
                        all_tar_waves.append(batch_tar_waves)
                        
                        # 每批次处理完清理一次显存碎片
                        if device == 'cuda' and b % 2 == 0:
                            torch.cuda.empty_cache()

                    tar_waves = torch.cat(all_tar_waves, dim=0)
                    del all_tar_waves
                    del spek
                    
                    tar_signal = (
                        tar_waves[:, :, trim:-trim]
                        .transpose(0, 1)
                        .reshape(2, -1)
                        .cpu()
                        .numpy()[:, :-pad]
                    )
                    
                    del tar_waves
                    if device == 'cuda':
                        torch.cuda.empty_cache()

                    if offset > 0:
                        tar_signal = tar_signal[:, offset : offset + base_n_sample]
                    else:
                        tar_signal = tar_signal[:, :base_n_sample]
                    
                    if total_tar_signal is None:
                        total_tar_signal = tar_signal
                    else:
                        total_tar_signal += tar_signal
            
            # 取 shifts 平均值
            tar_signal = total_tar_signal / shifts
            
            start = 0 if mix_offset == 0 else margin_size
            end = None if mix_offset == list(mixes.keys())[::-1][0] else -margin_size
            if margin_size == 0:
                end = None
            
            chunked_sources.append(tar_signal[:, start:end])
            progress_bar.update(1)
            
        _sources = np.concatenate(chunked_sources, axis=-1)
        progress_bar.close()
        return _sources

    def prediction(self, m, vocal_root, others_root, format, is_hp3=False):
        os.makedirs(vocal_root, exist_ok=True)
        os.makedirs(others_root, exist_ok=True)
        
        # 获取不带扩展名的基础文件名
        input_filename = os.path.basename(m)
        basename = input_filename
        audio_exts = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus")
        for ext in audio_exts:
            if basename.lower().endswith(ext):
                basename = basename[:-len(ext)]
                break
        if basename.endswith("."): basename = basename[:-1]
        
        mix, rate = librosa.load(m, mono=False, sr=44100)
        if mix.ndim == 1:
            mix = np.asfortranarray([mix, mix])
        mix = mix.T
        sources = self.demix(mix.T)
        opt = sources[0].T
        
        # is_hp3 决定了哪部分是人声，哪部分是伴奏
        # 对于 Inst 模型，默认 opt 是伴奏，mix - opt 是人声
        # 如果 is_hp3 为 True（某些模型可能需要反转），则交换
        vocal = mix - opt
        instrument = opt
        
        if is_hp3:
            vocal, instrument = instrument, vocal

        if format in ["wav", "flac"]:
            save_audio_robust(
                "%s/%s_main_vocal.%s" % (vocal_root, basename, format), vocal, rate
            )
            save_audio_robust("%s/%s_others.%s" % (others_root, basename, format), instrument, rate)
        else:
            path_vocal = "%s/%s_main_vocal.wav" % (vocal_root, basename)
            path_other = "%s/%s_others.wav" % (others_root, basename)
            save_audio_robust(path_vocal, vocal, rate)
            save_audio_robust(path_other, instrument, rate)
            opt_path_vocal = path_vocal[:-4] + ".%s" % format
            opt_path_other = path_other[:-4] + ".%s" % format
            if os.path.exists(path_vocal):
                os.system(
                    "ffmpeg -i %s -vn %s -q:a 2 -y" % (path_vocal, opt_path_vocal)
                )
                if os.path.exists(opt_path_vocal):
                    try:
                        os.remove(path_vocal)
                    except:
                        pass
            if os.path.exists(path_other):
                os.system(
                    "ffmpeg -i %s -vn %s -q:a 2 -y" % (path_other, opt_path_other)
                )
                if os.path.exists(opt_path_other):
                    try:
                        os.remove(path_other)
                    except:
                        pass


class MDXNetDereverb:
    def __init__(self, chunks, model_path, force_cpu=False):
        self.onnx = model_path
        self.force_cpu = force_cpu
        # 匹配 UVR5 的 Overlap/Shifts 设置
        # 增加 shifts 能显著减少残留，但会增加推理时间。
        # 4 是高质量推荐值，但在 API 中为了速度我们默认使用 2。
        self.shifts = 2 
        self.mixing = "min_mag"
        self.chunks = chunks
        self.margin = 44100
        # 匹配 UVR5 的 Segment Size 256
        self.dim_t = 8 
        self.dim_f = 3072
        self.n_fft = 6144
        # 开启 Denoise 是剥离干净的关键，特别是在处理高质量模型时
        # 注意：如果速度过慢，可以考虑关闭它，但这会牺牲伴奏的干净程度
        self.denoise = True 
        self.pred = Predictor(self)
        self.device = device

    def _path_audio_(self, input, others_root, vocal_root, format, is_hp3=False):
        # 4060 8GB 显存，直接将 chunks 设为 1。
        # 处理整首歌作为一整块，极大减少 STFT/ISTFT 重叠开销和数据同步开销。
        # 内部有 mini_batch_size=64 保证 ONNX 推理不会爆显存。
        self.chunks = 1
        self.shifts = 1 # 默认 1，去噪已足够干净，极大提升速度
        need_reformat = 1
        done = 0
        
        # 统一路径处理，避免双重扩展名或非法字符
        input_path = os.path.abspath(input)
        name = os.path.splitext(os.path.basename(input_path))[0]
        # 如果文件名中还带有 .mp3 等，再次剥离
        if "." in name:
            name = os.path.splitext(name)[0]
            
        # 确保输出目录存在
        os.makedirs(others_root, exist_ok=True)
        os.makedirs(vocal_root, exist_ok=True)
        try:
            info = ffmpeg.probe(input, cmd="ffprobe")
            if (
                info["streams"][0]["channels"] == 2
                and info["streams"][0]["sample_rate"] == "44100"
            ):
                need_reformat = 0
                self.pred.prediction(input, vocal_root, others_root, format, is_hp3=is_hp3)
                done = 1
        except:
            need_reformat = 1
            traceback.print_exc()
        if need_reformat == 1:
            tmp_path = "%s/%s.reformatted.wav" % (
                os.path.join(os.environ["TEMP"]),
                os.path.basename(input),
            )
            os.system(
                f'ffmpeg -i "{input}" -vn -acodec pcm_s16le -ac 2 -ar 44100 "{tmp_path}" -y'
            )
            input = tmp_path
        try:
            if done == 0:
                self.pred.prediction(input, vocal_root, others_root, format, is_hp3=is_hp3)
            print("%s->Success" % (os.path.basename(input)))

        except:
            print(
                "%s->%s" % (os.path.basename(input), traceback.format_exc())
            )

        
