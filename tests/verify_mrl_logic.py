
import sys
import os
import math
from dotenv import load_dotenv

sys.path.append(os.getcwd())

# Import the private function to test it
from llm.knowledge import _process_vector

def test_mrl_logic():
    print("🧪 Testing MRL (Matryoshka) Logic...")
    
    # 1. Create a dummy large vector (e.g. 10 dimensions, target 5)
    # Using small numbers to verify math easily
    large_vec = [1.0] * 10 # length 10
    target_dim = 5
    
    # 2. Process
    processed = _process_vector(large_vec, target_dim)
    
    # 3. Assertions
    print(f"Original len: {len(large_vec)}")
    print(f"Processed len: {len(processed)}")
    
    if len(processed) != target_dim:
        print(f"❌ FAILED: Exepected len {target_dim}, got {len(processed)}")
        sys.exit(1)
        
    # Check Normalization
    norm = math.sqrt(sum(x*x for x in processed))
    print(f"Norm L2: {norm}")
    
    if abs(norm - 1.0) > 1e-6:
        print(f"❌ FAILED: Norm is not 1.0 (got {norm})")
        sys.exit(1)
        
    print("✅ MRL Verification Successful!")

if __name__ == "__main__":
    test_mrl_logic()
