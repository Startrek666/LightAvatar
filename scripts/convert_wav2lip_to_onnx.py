"""
Wav2Lip PyTorch模型转ONNX格式脚本

用法:
    python scripts/convert_wav2lip_to_onnx.py

要求:
    - models/wav2lip/wav2lip.pth 存在
    - 已安装 torch, onnx, onnxruntime
"""

import torch
import torch.nn as nn
import onnx
import onnxruntime as ort
import numpy as np
from pathlib import Path
import sys

# Wav2Lip模型架构定义
class Conv2d(nn.Module):
    def __init__(self, cin, cout, kernel_size, stride, padding, residual=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conv_block = nn.Sequential(
            nn.Conv2d(cin, cout, kernel_size, stride, padding),
            nn.BatchNorm2d(cout)
        )
        self.act = nn.ReLU()
        self.residual = residual

    def forward(self, x):
        out = self.conv_block(x)
        if self.residual:
            out += x
        return self.act(out)


class Wav2Lip(nn.Module):
    def __init__(self):
        super(Wav2Lip, self).__init__()

        # Audio Encoder
        self.audio_encoder = nn.Sequential(
            Conv2d(1, 32, kernel_size=3, stride=1, padding=1),
            Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True),
            Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True),

            Conv2d(32, 64, kernel_size=3, stride=(3, 1), padding=1),
            Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
            Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),

            Conv2d(64, 128, kernel_size=3, stride=3, padding=1),
            Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
            Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),

            Conv2d(128, 256, kernel_size=3, stride=(3, 2), padding=1),
            Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),

            Conv2d(256, 512, kernel_size=3, stride=1, padding=0),
            Conv2d(512, 512, kernel_size=1, stride=1, padding=0),
        )

        # Face Encoder
        self.face_encoder_blocks = nn.ModuleList([
            nn.Sequential(Conv2d(6, 16, kernel_size=7, stride=1, padding=3)),

            nn.Sequential(
                Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
                Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
                Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
                Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                Conv2d(128, 256, kernel_size=3, stride=2, padding=1),
                Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                Conv2d(256, 512, kernel_size=3, stride=2, padding=1),
                Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                Conv2d(512, 512, kernel_size=3, stride=1, padding=0),
                Conv2d(512, 512, kernel_size=1, stride=1, padding=0)),
        ])

        # Face Decoder
        self.face_decoder_blocks = nn.ModuleList([
            nn.Sequential(
                Conv2d(512, 512, kernel_size=1, stride=1, padding=0)),

            nn.Sequential(
                nn.ConvTranspose2d(1024, 512, kernel_size=3, stride=1, padding=0),
                Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                nn.ConvTranspose2d(1024, 512, kernel_size=3, stride=2, padding=1, output_padding=1),
                Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                nn.ConvTranspose2d(768, 384, kernel_size=3, stride=2, padding=1, output_padding=1),
                Conv2d(384, 384, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(384, 384, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                nn.ConvTranspose2d(512, 256, kernel_size=3, stride=2, padding=1, output_padding=1),
                Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                nn.ConvTranspose2d(320, 128, kernel_size=3, stride=2, padding=1, output_padding=1),
                Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True)),

            nn.Sequential(
                nn.ConvTranspose2d(160, 64, kernel_size=3, stride=2, padding=1, output_padding=1),
                Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
                Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True)),
        ])

        self.output_block = nn.Sequential(
            Conv2d(80, 32, kernel_size=3, stride=1, padding=1),
            nn.Conv2d(32, 3, kernel_size=1, stride=1, padding=0),
            nn.Sigmoid()
        )

    def forward(self, audio_sequences, face_sequences):
        # B, 1, 80, 16
        audio_embedding = self.audio_encoder(audio_sequences)

        feats = []
        x = face_sequences
        for f in self.face_encoder_blocks:
            x = f(x)
            feats.append(x)

        x = audio_embedding
        for f in self.face_decoder_blocks:
            x = f(x)
            try:
                x = torch.cat((x, feats[-1]), dim=1)
            except Exception as e:
                print(x.size())
                print(feats[-1].size())
                raise e

            feats.pop()

        x = self.output_block(x)

        return x


def load_checkpoint(path, device='cpu'):
    """加载PyTorch检查点"""
    print(f"加载模型检查点: {path}")
    checkpoint = torch.load(path, map_location=device)
    return checkpoint


def convert_to_onnx():
    """转换Wav2Lip模型为ONNX格式"""
    
    # 路径配置
    pytorch_model_path = Path('models/wav2lip/wav2lip.pth')
    onnx_model_path = Path('models/wav2lip/wav2lip.onnx')
    
    # 检查PyTorch模型是否存在
    if not pytorch_model_path.exists():
        print(f"错误: 未找到PyTorch模型文件 {pytorch_model_path}")
        print("请先运行 scripts/download_models.sh 下载模型")
        return False
    
    print("="*60)
    print("Wav2Lip PyTorch -> ONNX 转换工具")
    print("="*60)
    print()
    
    # 创建模型
    print("1. 创建模型架构...")
    model = Wav2Lip()
    
    # 加载权重
    print("2. 加载模型权重...")
    checkpoint = load_checkpoint(pytorch_model_path, device='cpu')
    
    # 检查checkpoint结构
    if 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict)
    model.eval()
    
    print(f"   模型参数数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 准备示例输入
    print("3. 准备示例输入...")
    batch_size = 1
    audio_input = torch.randn(batch_size, 1, 80, 16)  # (B, 1, 80, 16)
    face_input = torch.randn(batch_size, 6, 96, 96)   # (B, 6, 96, 96)
    
    # 测试前向传播
    print("4. 测试模型前向传播...")
    with torch.no_grad():
        output = model(audio_input, face_input)
    print(f"   输入形状: audio={audio_input.shape}, face={face_input.shape}")
    print(f"   输出形状: {output.shape}")
    
    # 导出为ONNX
    print("5. 导出为ONNX格式...")
    torch.onnx.export(
        model,
        (audio_input, face_input),
        str(onnx_model_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['audio', 'face'],
        output_names=['output'],
        dynamic_axes={
            'audio': {0: 'batch_size'},
            'face': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )
    
    print(f"   ✓ ONNX模型已保存: {onnx_model_path}")
    print(f"   文件大小: {onnx_model_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 验证ONNX模型
    print("6. 验证ONNX模型...")
    onnx_model = onnx.load(str(onnx_model_path))
    onnx.checker.check_model(onnx_model)
    print("   ✓ ONNX模型验证通过")
    
    # 测试ONNX推理
    print("7. 测试ONNX Runtime推理...")
    ort_session = ort.InferenceSession(str(onnx_model_path))
    
    # 准备输入
    ort_inputs = {
        'audio': audio_input.numpy(),
        'face': face_input.numpy()
    }
    
    # 运行推理
    ort_outputs = ort_session.run(None, ort_inputs)
    
    print(f"   ✓ ONNX推理输出形状: {ort_outputs[0].shape}")
    
    # 比较输出
    print("8. 比较PyTorch和ONNX输出...")
    diff = np.abs(output.numpy() - ort_outputs[0])
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    print(f"   最大差异: {max_diff:.6f}")
    print(f"   平均差异: {mean_diff:.6f}")
    
    if max_diff < 1e-4:
        print("   ✓ 输出一致性验证通过")
    else:
        print("   ⚠ 输出存在较大差异，请检查")
    
    print()
    print("="*60)
    print("转换完成！")
    print("="*60)
    print()
    print(f"ONNX模型路径: {onnx_model_path}")
    print()
    print("使用方法:")
    print("  在 config/config.yaml 中确保 avatar.use_onnx 设置为 true")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = convert_to_onnx()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
