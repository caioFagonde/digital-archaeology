use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyIOError};
use memmap2::MmapOptions;
use std::fs::File;
use aho_corasick::AhoCorasick;
use serde::Deserialize;

#[derive(Deserialize)]
struct RuleDef {
    name: String,
    hex: String,
}

#[pyclass]
pub struct ChunkStats {
    #[pyo3(get)]
    pub data: Vec<u8>,
    #[pyo3(get)]
    pub entropy: f64,
    #[pyo3(get)]
    pub histogram: Vec<u64>,
    #[pyo3(get)]
    pub matches: Vec<(String, usize)>, // (Rule Name, Absolute Offset)
}

#[pyclass]
pub struct Engine {
    mmap: memmap2::Mmap,
    file_size: usize,
    ac: Option<AhoCorasick>,
    rule_names: Vec<String>,
}

/// Helper function to convert a string like "50 4B 03 04" into bytes.
fn parse_hex(hex_str: &str) -> Vec<u8> {
    let cleaned: String = hex_str.chars().filter(|c| !c.is_whitespace()).collect();
    (0..cleaned.len())
        .step_by(2)
        .filter_map(|i| u8::from_str_radix(&cleaned[i..i + 2], 16).ok())
        .collect()
}

#[pymethods]
impl Engine {
    #[new]
    pub fn new(file_path: &str) -> PyResult<Self> {
        let file = File::open(file_path)?;
        let mmap = unsafe { MmapOptions::new().map(&file)? };
        let file_size = mmap.len();
        
        Ok(Engine { 
            mmap, 
            file_size,
            ac: None,
            rule_names: Vec::new(),
        })
    }

    /// Loads JSON rules and compiles the Aho-Corasick automaton.
    pub fn load_rules(&mut self, rules_path: &str) -> PyResult<()> {
        let file = File::open(rules_path).map_err(|e| PyIOError::new_err(e.to_string()))?;
        let rules: Vec<RuleDef> = serde_json::from_reader(file)
            .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

        let mut patterns = Vec::new();
        self.rule_names.clear();

        for rule in rules {
            patterns.push(parse_hex(&rule.hex));
            self.rule_names.push(rule.name);
        }

        if !patterns.is_empty() {
            let ac = AhoCorasick::new(patterns)
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
            self.ac = Some(ac);
        }

        Ok(())
    }

    pub fn get_file_size(&self) -> usize {
        self.file_size
    }

    pub fn get_chunk_stats(&self, offset: usize, size: usize) -> PyResult<ChunkStats> {
        if offset >= self.file_size {
            return Err(PyValueError::new_err("Offset out of bounds"));
        }
        
        let end = std::cmp::min(offset + size, self.file_size);
        let chunk = &self.mmap[offset..end];
        
        // 1. Calculate Histogram & Entropy
        let mut histogram = vec![0u64; 256];
        for &byte in chunk {
            histogram[byte as usize] += 1;
        }
        
        let mut entropy = 0.0;
        let chunk_len = chunk.len() as f64;
        if chunk_len > 0.0 {
            for &count in &histogram {
                if count > 0 {
                    let p = count as f64 / chunk_len;
                    entropy -= p * p.log2();
                }
            }
        }

        // 2. Scan for Signatures
        let mut matches = Vec::new();
        if let Some(ac) = &self.ac {
            for mat in ac.find_iter(chunk) {
                let rule_name = self.rule_names[mat.pattern()].clone();
                let absolute_offset = offset + mat.start();
                matches.push((rule_name, absolute_offset));
            }
        }
        
        Ok(ChunkStats {
            data: chunk.to_vec(),
            entropy,
            histogram,
            matches,
        })
    }
}

/// REQUIRED: The PyO3 module initialization block that exports the module to Python.
#[pymodule]
fn archaeology_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Engine>()?;
    m.add_class::<ChunkStats>()?;
    Ok(())
}