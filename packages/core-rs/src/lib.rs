use pyo3::prelude::*;

/// Computes Z-score anomaly detection.
/// Returns a list of booleans indicating if each point is an anomaly.
/// Computes Z-score anomaly detection for the last element in a sliding window.
/// Returns a tuple: (is_anomaly, mean, std_dev, z_score)
#[pyfunction]
fn detect_anomaly_last(data: Vec<f64>, threshold: f64) -> (bool, f64, f64, f64) {
    if data.len() < 2 {
        return (false, 0.0, 0.0, 0.0);
    }
    
    // Calculate mean of all elements EXCEPT the last one (historical window)
    let hist_len = data.len() - 1;
    let sum: f64 = data.iter().take(hist_len).sum();
    let mean = sum / hist_len as f64;
    
    // Calculate std dev
    let variance_sum: f64 = data.iter().take(hist_len).map(|value| {
        let diff = mean - *value;
        diff * diff
    }).sum();
    let variance = variance_sum / hist_len as f64;
    let std_dev = variance.sqrt();
    
    let last_val = *data.last().unwrap();
    let mut z_score = 0.0;
    let mut is_anomaly = false;
    
    if std_dev > 0.0 {
        z_score = (last_val - mean).abs() / std_dev;
        is_anomaly = z_score > threshold;
    }
    
    (is_anomaly, mean, std_dev, z_score)
}

/// A Python module implemented in Rust.
#[pymodule]
fn geoweather_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(detect_anomaly_last, m)?)?;
    Ok(())
}
