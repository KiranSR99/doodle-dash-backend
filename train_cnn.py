import numpy as np
import datetime
import os
from tqdm import tqdm
import time

# =======================
# 1. Optimized Data Loading
# =======================
def load_data(classes, samples_per_class=6000, base_dir="data"):
    X, y = [], []
    print(f"Loading data from: {base_dir}")
    
    for label, cls in enumerate(classes):
        path = os.path.join(base_dir, f"{cls}.npy")
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        
        # Load and randomly sample for better diversity
        all_data = np.load(path)
        if len(all_data) > samples_per_class:
            indices = np.random.choice(len(all_data), samples_per_class, replace=False)
            data = all_data[indices]
        else:
            data = all_data
            
        X.append(data)
        y.append(np.full(len(data), label))
        print(f"Loaded {cls}: {len(data)} samples")

    X = np.concatenate(X, axis=0)
    y = np.concatenate(y, axis=0)

    # Normalize & reshape - use float32 for speed
    X = (X.astype(np.float32) / 255.0).reshape(-1, 1, 28, 28)

    # Shuffle
    indices = np.arange(len(X))
    np.random.shuffle(indices)
    return X[indices], y[indices]

# =======================
# 2. Mini-Batch Processing
# =======================
def create_mini_batches(X, y, batch_size=32):
    """Create mini-batches for faster training"""
    indices = np.arange(len(X))
    np.random.shuffle(indices)
    
    batches_X, batches_y = [], []
    for i in range(0, len(X), batch_size):
        batch_indices = indices[i:i+batch_size]
        batches_X.append(X[batch_indices])
        batches_y.append(y[batch_indices])
    return batches_X, batches_y

# =======================
# 3. Optimized Layers
# =======================
class Conv3x3:
    def __init__(self, num_filters):
        self.num_filters = num_filters
        # Better initialization - He initialization for ReLU
        self.filters = (np.random.randn(num_filters, 1, 3, 3) * np.sqrt(2.0/9)).astype(np.float32)

    def iterate_regions(self, image):
        num_filters, h, w = image.shape
        for i in range(h - 2):
            for j in range(w - 2):
                region = image[:, i:(i+3), j:(j+3)]
                yield i, j, region

    def forward(self, input):
        self.last_input = input
        num_filters, h, w = input.shape
        output = np.zeros((self.num_filters, h - 2, w - 2), dtype=np.float32)
        for f in range(self.num_filters):
            for i, j, region in self.iterate_regions(input):
                output[f, i, j] = np.sum(region * self.filters[f])
        return output

    def backprop(self, d_L_d_out, learn_rate):
        d_L_d_filters = np.zeros(self.filters.shape, dtype=np.float32)
        for f in range(self.num_filters):
            for i, j, region in self.iterate_regions(self.last_input):
                d_L_d_filters[f] += d_L_d_out[f, i, j] * region
        self.filters -= learn_rate * d_L_d_filters
        return None

class MaxPool2:
    def iterate_regions(self, image):
        num_filters, h, w = image.shape
        new_h = h // 2
        new_w = w // 2
        for i in range(new_h):
            for j in range(new_w):
                start_i, start_j = i * 2, j * 2
                region = image[:, start_i:start_i+2, start_j:start_j+2]
                yield i, j, region

    def forward(self, input):
        self.last_input = input
        num_filters, h, w = input.shape
        new_h = h // 2
        new_w = w // 2
        output = np.zeros((num_filters, new_h, new_w), dtype=np.float32)
        for i, j, region in self.iterate_regions(input):
            output[:, i, j] = np.max(region, axis=(1, 2))
        return output

    def backprop(self, d_L_d_out):
        return None

class Dense:
    def __init__(self, in_len, out_len):
        # Improved initialization - Xavier/He for better convergence
        self.weights = (np.random.randn(in_len, out_len) * np.sqrt(2.0/in_len)).astype(np.float32)
        self.biases = np.zeros(out_len, dtype=np.float32)

    def forward(self, input):
        self.last_input_shape = input.shape
        input = input.flatten()
        self.last_input = input
        output = np.dot(input, self.weights) + self.biases
        return output

    def backprop(self, d_L_d_out, learn_rate):
        d_L_d_w = np.outer(self.last_input, d_L_d_out)
        d_L_d_b = d_L_d_out.copy()
        d_L_d_input = np.dot(self.weights, d_L_d_out)
        
        self.weights -= learn_rate * d_L_d_w
        self.biases -= learn_rate * d_L_d_b
        return d_L_d_input.reshape(self.last_input_shape)

# =======================
# 4. Activation & Loss Functions
# =======================
def softmax(x):
    # Numerically stable softmax
    exp_x = np.exp(x - np.max(x))
    return exp_x / np.sum(exp_x)

def cross_entropy(pred, label):
    return -np.log(np.clip(pred[label], 1e-15, 1.0))

def accuracy(preds, labels):
    return np.mean(preds == labels)

def relu(x):
    return np.maximum(0, x)

def relu_derivative(x):
    return (x > 0).astype(np.float32)

# =======================
# 5. Optimized CNN Model
# =======================
class OptimizedCNN:
    def __init__(self):
        # Balanced model size for speed vs accuracy
        self.conv1 = Conv3x3(8)    # 8 filters
        self.pool1 = MaxPool2()
        self.conv2 = Conv3x3(16)   # 16 filters
        self.pool2 = MaxPool2()
        self.fc1 = Dense(16*5*5, 64)  # 64 neurons
        self.fc2 = Dense(64, 8)       # 8 classes

    def forward(self, image):
        out1 = self.conv1.forward(image)
        out1_relu = relu(out1)
        out2 = self.pool1.forward(out1_relu)
        out3 = self.conv2.forward(out2)
        out3_relu = relu(out3)
        out4 = self.pool2.forward(out3_relu)
        out5 = self.fc1.forward(out4)
        out5_relu = relu(out5)
        out6 = self.fc2.forward(out5_relu)
        return softmax(out6)

    def train_step(self, image, label, lr):
        # Forward pass
        out1 = self.conv1.forward(image)
        out1_relu = relu(out1)
        out2 = self.pool1.forward(out1_relu)
        out3 = self.conv2.forward(out2)
        out3_relu = relu(out3)
        out4 = self.pool2.forward(out3_relu)
        out5 = self.fc1.forward(out4)
        out5_relu = relu(out5)
        out6 = self.fc2.forward(out5_relu)
        probs = softmax(out6)

        loss = cross_entropy(probs, label)
        
        # Backward pass
        d_L_d_out = probs.copy()
        d_L_d_out[label] -= 1

        grad = self.fc2.backprop(d_L_d_out, lr)
        grad = grad * relu_derivative(out5)
        grad = self.fc1.backprop(grad, lr)

        return loss, np.argmax(probs)

    def train_batch(self, batch_X, batch_y, lr):
        """Train on a batch of samples"""
        total_loss = 0
        correct_preds = 0
        
        for i in range(len(batch_X)):
            loss, pred = self.train_step(batch_X[i], batch_y[i], lr)
            total_loss += loss
            if pred == batch_y[i]:
                correct_preds += 1
                
        return total_loss / len(batch_X), correct_preds / len(batch_X)

    def save(self, path):
        np.savez_compressed(path,
                 conv1_filters=self.conv1.filters,
                 conv2_filters=self.conv2.filters,
                 fc1_weights=self.fc1.weights, fc1_biases=self.fc1.biases,
                 fc2_weights=self.fc2.weights, fc2_biases=self.fc2.biases)

    def load(self, path):
        data = np.load(path)
        self.conv1.filters = data['conv1_filters']
        self.conv2.filters = data['conv2_filters']
        self.fc1.weights = data['fc1_weights']
        self.fc1.biases = data['fc1_biases']
        self.fc2.weights = data['fc2_weights']
        self.fc2.biases = data['fc2_biases']

# =======================
# 6. Training Pipeline
# =======================
def train_model():
    print("CNN Training Started")
    print("="*50)
    
    # 8 classes for balanced training
    classes = ["butterfly", "envelope", "fish", "flower", "leaf", "mountain", "star", "tree"]
    
    # Load data
    print("Loading dataset...")
    start_time = time.time()
    X, y = load_data(classes, samples_per_class=6000)
    load_time = time.time() - start_time
    print(f"Loaded {len(X)} samples in {load_time:.2f} seconds")

    # Train/validation split (85% train, 15% validation)
    split = int(0.85 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    print(f"Training: {len(X_train)} samples, Validation: {len(X_val)} samples")

    # Initialize model
    model = OptimizedCNN()
    
    # Setup logging
    os.makedirs("model", exist_ok=True)
    log_file_path = os.path.join("model", "training_log.txt")
    log_file = open(log_file_path, "w")
    log_file.write(f"Training Started: {datetime.datetime.now()}\n")
    log_file.write(f"Dataset: {len(X_train)} train, {len(X_val)} validation\n")
    log_file.write("="*50 + "\n")
    
    # Training parameters
    epochs = 12
    batch_size = 32
    lr_schedule = [0.02, 0.02, 0.015, 0.015, 0.01, 0.01, 0.008, 0.008, 0.005, 0.005, 0.003, 0.003]
    
    print(f"Epochs: {epochs}, Batch Size: {batch_size}")
    
    # Training variables
    training_start = time.time()
    best_val_acc = 0.0
    
    for epoch in range(epochs):
        epoch_start = time.time()
        lr = lr_schedule[epoch]
        
        # Create mini-batches for this epoch
        batch_X, batch_y = create_mini_batches(X_train, y_train, batch_size)
        
        print(f"\nEpoch {epoch+1}/{epochs} (LR: {lr})")
        
        # Training with batch processing
        epoch_losses = []
        epoch_accs = []
        
        pbar = tqdm(range(len(batch_X)), desc="Training")
        for i in pbar:
            batch_loss, batch_acc = model.train_batch(batch_X[i], batch_y[i], lr)
            epoch_losses.append(batch_loss)
            epoch_accs.append(batch_acc)
            
            # Update progress every 20 batches
            if i % 20 == 0 and len(epoch_losses) >= 20:
                recent_loss = np.mean(epoch_losses[-20:])
                recent_acc = np.mean(epoch_accs[-20:])
                pbar.set_postfix({
                    'Loss': f'{recent_loss:.3f}',
                    'Acc': f'{recent_acc:.3f}'
                })

        # Validation phase
        print("Validating...")
        val_preds = []
        val_sample_size = min(3000, len(X_val))
        val_indices = np.random.choice(len(X_val), val_sample_size, replace=False)
        
        for i in tqdm(val_indices, desc="Validation", leave=False):
            pred = np.argmax(model.forward(X_val[i]))
            val_preds.append(pred)
            
        val_acc = accuracy(np.array(val_preds), y_val[val_indices])
        train_acc = np.mean(epoch_accs)
        mean_loss = np.mean(epoch_losses)
        epoch_time = time.time() - epoch_start
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_path = os.path.join("model", "best_model.npz")
            model.save(best_model_path)
            print(f"New best model saved! Val Acc: {val_acc:.4f}")
            
        # Epoch summary
        epoch_summary = (f"Epoch {epoch+1}: "
                        f"Loss={mean_loss:.4f}, "
                        f"Train_Acc={train_acc:.4f}, "
                        f"Val_Acc={val_acc:.4f}, "
                        f"Time={epoch_time:.1f}s")
        
        print(epoch_summary)
        log_file.write(epoch_summary + "\n")
        log_file.flush()
        
        # Save checkpoint
        checkpoint_path = os.path.join("model", f"checkpoint_epoch_{epoch+1}.npz")
        model.save(checkpoint_path)

    # Final model save
    final_model_path = os.path.join("model", "final_model.npz")
    model.save(final_model_path)
    
    # Training completion summary
    total_time = time.time() - training_start
    hours = total_time / 3600
    
    print("\n" + "="*50)
    print("TRAINING COMPLETED!")
    print(f"Total Time: {total_time:.1f} seconds ({hours:.2f} hours)")
    print(f"Best Validation Accuracy: {best_val_acc:.4f} ({best_val_acc*100:.1f}%)")
    print(f"Models saved in 'model/' directory")
    print("="*50)
    
    # Final log entries
    log_file.write("="*50 + "\n")
    log_file.write(f"Training completed: {datetime.datetime.now()}\n")
    log_file.write(f"Total time: {total_time:.1f}s ({hours:.2f}h)\n")
    log_file.write(f"Best validation accuracy: {best_val_acc:.4f}\n")
    log_file.close()
    
    return model, best_val_acc

# =======================
# 7. Quick Model Test Function
# =======================
def test_model(model_path, X_test, y_test, classes, num_samples=1000):
    """Quick test of trained model"""
    print(f"Testing model: {model_path}")
    
    model = OptimizedCNN()
    model.load(model_path)
    
    # Test on random sample
    test_indices = np.random.choice(len(X_test), min(num_samples, len(X_test)), replace=False)
    predictions = []
    
    for i in tqdm(test_indices, desc="Testing"):
        pred = np.argmax(model.forward(X_test[i]))
        predictions.append(pred)
    
    test_acc = accuracy(np.array(predictions), y_test[test_indices])
    print(f"Test Accuracy: {test_acc:.4f} ({test_acc*100:.1f}%)")
    
    return test_acc

# =======================
# 8. Main Execution
# =======================
if __name__ == "__main__":
    print("Starting CNN Training Pipeline")
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Train the model
    trained_model, best_accuracy = train_model()
    
    print(f"\nTraining completed! Best model achieved {best_accuracy*100:.1f}% accuracy.")