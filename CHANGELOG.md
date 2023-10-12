# Change Log
All notable changes to this project will be documented in this file.
 
## [0.1.0] - 2017-03-15

First release of `dtaianomaly`! While our toolbox is still a work in progress, we believe it is already in a usable stage. Additionally, by publicly releasing `dtaianomaly`, we hope to receive feedback from the community!

### Added
- `anomaly_detection`: a module for time series anomaly detection algorithms. Currently, basic algorithms using the [PyOD library](https://github.com/yzhao062/pyod) are included, but we plan to extend on this in the future!
- `data_management`: a module to easily handle datasets. You can filter the datasets on certain properties and add new datasets through a few simple function calls! Go to the corresponding [README](https://gitlab.kuleuven.be/u0143709/dtaianomaly/-/blob/main/data/README.md) for more information. 
- `evaluation`: It is crucial to evaluate an anomaly detector in order to quantify its performance. This module offers several metrics to this end. Currently, only relative simple methods are included, but we plan to extend this repository with more recently proposed approaches. 
- `visualization`: This module allows to easily visualize the data and anomalies, as time series and anomalies inherently are great for visual inspection.
- `workflow`: This module allows to benchmark an algorithm on a larger set of datasets, through configuration files. This methodology ensures reproducability by simply providing the configuration files! 
 
### Changed
 
### Fixed