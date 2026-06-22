# -*- coding: utf-8 -*-
"""
PyTorch 多因子选股模型
======================
"""
import torch
import torch.nn as nn
import numpy as np
import os

class QuantFactorModel(nn.Module):
    """多因子选股模型"""
    
    def __init__(self, n_factors=14):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_factors, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1)
        )
    
    def forward(self, x):
        return self.net(x)


class ModelTrainer:
    """模型训练器"""
    
    def __init__(self, n_factors=14, model_dir=None):
        self.n_factors = n_factors
        self.model = QuantFactorModel(n_factors)
        self.device = torch.device('cpu')
        
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(__file__), 'models')
        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, 'factor_model.pt')
        
        # 加载已有模型
        if os.path.exists(self.model_path):
            self.load_model()
    
    def train(self, X_train, y_train, epochs=200, lr=0.001, weight_decay=1e-4):
        """训练模型"""
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=weight_decay)
        criterion = nn.MSELoss()
        
        X_tensor = torch.FloatTensor(X_train).to(self.device)
        y_tensor = torch.FloatTensor(y_train).reshape(-1, 1).to(self.device)
        
        losses = []
        for epoch in range(epochs):
            optimizer.zero_grad()
            output = self.model(X_tensor)
            loss = criterion(output, y_tensor)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            
            if (epoch + 1) % 50 == 0:
                print(f"  Epoch {epoch+1}/{epochs}  Loss: {loss.item():.6f}")
        
        self.save_model()
        return losses
    
    def predict(self, X):
        """预测"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            scores = self.model(X_tensor).numpy().flatten()
        return scores
    
    def save_model(self):
        """保存模型"""
        os.makedirs(self.model_dir, exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        print(f"  Model saved to {self.model_path}")
    
    def load_model(self):
        """加载模型"""
        if os.path.exists(self.model_path):
            self.model.load_state_dict(torch.load(self.model_path, weights_only=True))
            self.model.eval()
            print(f"  Model loaded from {self.model_path}")
