import os
import time
import tracemalloc
import json
import multiprocessing
from typing import Union, Optional, List, Dict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from dtaianomaly.data_management.DataManager import DataManager, DatasetIndex
from dtaianomaly.anomaly_detection import TimeSeriesAnomalyDetector
from dtaianomaly.anomaly_detection.utility.TrainType import TrainType

from dtaianomaly.evaluation.Metric import Metric
from dtaianomaly.visualization import plot_anomaly_scores

from dtaianomaly.workflow.handle_data_configuration import DataConfiguration, handle_data_configuration
from dtaianomaly.workflow.handle_algorithm_configuration import AlgorithmConfiguration, handle_algorithm_configuration
from dtaianomaly.workflow.handle_metric_configuration import MetricConfiguration, handle_metric_configuration
from dtaianomaly.workflow.handle_output_configuration import PlainOutputConfiguration, OutputConfiguration, handle_output_configuration


def __log(message: str, print_message: bool) -> None:
    if print_message:
        print(message)


def execute_algorithms(data_manager: DataManager,
                       data_configuration: DataConfiguration,
                       algorithm_configuration: AlgorithmConfiguration,
                       metric_configuration: MetricConfiguration,
                       output_configuration: Union[PlainOutputConfiguration, OutputConfiguration],
                       seed: Optional[int] = 0,
                       n_jobs: int = 1) -> Dict[str, pd.DataFrame]:
    """
    Execute a workflow, i.e., use one or more anomaly detectors to detect anomalies
    in a number of time series and save the results.

    Parameters
    ----------
    data_manager : :py:class:`~dtaianomaly.data_management.DataManager`
        The :py:class:`~dtaianomaly.data_management.DataManager` object that is
        used to read all the time series data.
    data_configuration : Dict[str, Any] or str
        The data configuration, used to select the time series in which anomalies
        will be detected in this workflow. If a string is provided, it represents
        a path to the configuration file in json format.
    algorithm_configuration : Dict[str, Any], str or Tuple[:py:class:`~dtaianomaly.anomaly_detection.TimeSeriesAnomalyDetector`, str]
        The algorithm configuration, used to load the required anomaly detectors to
        test in this workflow. If a string is provided, it represents a path to the
        configuration file in json format. Alternatively, a :py:class:`~dtaianomaly.anomaly_detection.TimeSeriesAnomalyDetector`
        can be used in combination with a str, which means that a specific anomaly
        detector, with its name, is provided.
    metric_configuration : Dict[str, Any] or str
        The metric configuration, used to load various evaluation metrics which
        will quantify the performance of the anomaly detector. If a string is
        provided, it represents a path to the configuration file in json format.
    output_configuration : Dict[str, Any], str or :py:class:`~dtaianomaly.workflow.OutputConfiguration`
        The output configuration, used to decide which information should be
        outputted during the workflow. If a string is provided, it represents
        a path to the configuration file in json format. Alternatively, a :py:class:`~dtaianomaly.workflow.OutputConfiguration`
        can be given directly, which encapsulates all possible settings on
        how the workflow will output information.
    seed : int, Optional, default = 0
        The random seed, which is set before the execution of each algorithm on
        each time series. By default, seed 0 will be used to guarantee reproducible
        experiments. If the seed is explicitly set to ``None``, only then no
        seed is used.
    n_jobs : int, default = 1
        The number of parallel jobs to use. This can hugely reduce the required running
        time because the algorithm can detect anomalies in multiple time series simultaneously.
        The detectors themselves will only use a single core for detecting anomalies in a
        single time series.

    Note
    ----
    - Please visit `this webpage <https://u0143709.pages.gitlab.kuleuven.be/dtaianomaly/getting_started/large_scale_experiments.html#configuration-files>`_
      for more information regarding the format of the different configuration files.
    - The configuration files equal dictionaries, with as keys the different properties
      that can be configured and as values the corresponding value to which the
      property is configured.
    - the workflow will have several other effects, beside generating the results and
      returning them. This includes generating files and storing various results,
      depending on the ``output_configuration`` parameter.

    Returns
    -------
    Dict[str, pd.DataFrame]
        A dictionary containing the results of the workflow. Each key equals the name of
        an anomaly detector, and the corresponding dataframe contains the concrete results
        of the algorithm for each time series.
    """
    data_manager = handle_data_configuration(data_manager, data_configuration)
    algorithms = handle_algorithm_configuration(algorithm_configuration)
    metrics = handle_metric_configuration(metric_configuration)

    all_results = {}
    for algorithm_name, (algorithm, algorithm_configuration) in algorithms.items():

        output_configuration_algorithm = handle_output_configuration(output_configuration, algorithm_name)
        __log(message=f'>>> Starting the workflow for {algorithm_name}',
              print_message=output_configuration_algorithm.verbose)

        with open(f'{output_configuration_algorithm.directory}/algorithm_config.json', 'w+') as algorithm_config_file:
            json.dump(algorithm_configuration, algorithm_config_file, indent=2)

        results_columns = ['Seed']
        results_columns += list(metrics.keys())
        if output_configuration_algorithm.trace_time:
            results_columns += ['Time fit (s)', 'Time predict (s)']
        if output_configuration_algorithm.trace_memory:
            results_columns += ['Peak memory fit (KiB)', 'Peak memory predict (KiB)']

        results = pd.DataFrame(
            index=pd.MultiIndex.from_tuples(data_manager.get(), names=['collection_name', 'dataset_name']),
            columns=results_columns
        )
        # Append to the existing results
        if os.path.exists(output_configuration_algorithm.results_path):
            existing_results = pd.read_csv(output_configuration_algorithm.results_path, index_col=['collection_name', 'dataset_name'])
            results = results.fillna(existing_results).combine_first(existing_results)

        __log(message=f">>> Iterating over the datasets\n"
                      f"Total number of datasets: {len(data_manager.get())}",
              print_message=output_configuration_algorithm.verbose)
        all_dataset_results: List[pd.Series] = []
        if n_jobs > 1:
            jobs = [
                (data_manager, dataset_index, algorithm, output_configuration_algorithm, metrics, results_columns, seed)
                for dataset_index in data_manager.get()
            ]
            with multiprocessing.Pool(n_jobs) as pool:
                all_dataset_results = pool.starmap(__detect_anomalies, jobs)
        else:
            for dataset_index in data_manager.get():
                all_dataset_results.append(__detect_anomalies(
                    data_manager=data_manager,
                    dataset_index=dataset_index,
                    algorithm=algorithm,
                    output_configuration=output_configuration_algorithm,
                    metrics=metrics,
                    results_columns=results_columns,
                    seed=seed
                ))

        __log(message=f">>> Formatting the results of the individual datasets", print_message=output_configuration_algorithm.verbose)
        for dataset_result in all_dataset_results:
            results.at[dataset_result.name] = dataset_result

        # Save the results, if requested
        if output_configuration_algorithm.save_results:
            __log(message=f">>> Saving the results to disk\n"
                          f"path: {output_configuration_algorithm.results_path}",
                  print_message=output_configuration_algorithm.verbose)
            results.to_csv(output_configuration_algorithm.results_path)

            if output_configuration_algorithm.constantly_save_results:
                __log(message=f">>> Cleaning up the intermediate files",
                      print_message=output_configuration_algorithm.verbose)
                for dataset_index in data_manager.get():
                    # Check if the file exists, because an error might be thrown
                    if os.path.isfile(output_configuration_algorithm.intermediate_results_path(dataset_index)):
                        os.remove(output_configuration_algorithm.intermediate_results_path(dataset_index))

        if output_configuration_algorithm.print_results:
            __log(message=f">>> Printing the results to the output stream", print_message=output_configuration_algorithm.verbose)
            print(results)

        all_results[algorithm_name] = results

    return all_results


def __detect_anomalies(
        data_manager: DataManager,
        dataset_index: DatasetIndex,
        algorithm: TimeSeriesAnomalyDetector,
        output_configuration: OutputConfiguration,
        metrics: Dict[str, Metric],
        results_columns: List[str],
        seed: int) -> pd.Series:

    __log(message=f">>> Handling dataset '{dataset_index}'", print_message=output_configuration.verbose)
    results = pd.Series(name=dataset_index, index=results_columns, dtype=float)

    __log(message=f">> Checking  algorithm-dataset compatibility", print_message=output_configuration.verbose)
    algorithm_train_type = algorithm.train_type()
    meta_data = data_manager.get_metadata(dataset_index)
    if not algorithm_train_type.can_solve_train_type_data(meta_data['train_type']):
        __log(message=f"The algorithm is not compatible with dataset {dataset_index}\n"
                      f"Algorithm type: {algorithm_train_type}\n"
                      f"Dataset type: {meta_data['train_type']}\n"
                      f"An error will be raised: {output_configuration.invalid_train_type_raise_error}",
              print_message=output_configuration.verbose)
        if output_configuration.invalid_train_type_raise_error:
            raise Exception(f"Algorithm type '{algorithm_train_type}' can not solve dataset type '{meta_data['train_type']}'!")
        else:
            return pd.Series(index=results_columns)

    __log(message=f">> Loading the train data", print_message=output_configuration.verbose)
    # For supervised algorithms, the ground truth of the train data is required
    if algorithm_train_type == TrainType.SUPERVISED:
        __log(message=f"Using train data and labels for supervised algorithm", print_message=output_configuration.verbose)
        data_train, ground_truth_train = data_manager.load_raw_data(dataset_index, train=True)

    # For semi-supervised algorithms, train data is required but not its ground truth, because
    # semi-supervised algorithms assume that the given data is normal
    elif algorithm_train_type == TrainType.SEMI_SUPERVISED:
        __log(message=f"Using train data but no labels for semi-supervised algorithm", print_message=output_configuration.verbose)
        data_train, _ = data_manager.load_raw_data(dataset_index, train=True)
        ground_truth_train = None

    # For unsupervised algorithms, use the train data to fit, if available, and otherwise use
    # the test data, but no labels are provided
    else:
        if meta_data['train_type'] == 'unsupervised':
            __log(message=f"Using **test** data but no labels for unsupervised algorithm", print_message=output_configuration.verbose)
            data_train, _ = data_manager.load_raw_data(dataset_index, train=False)
        else:
            __log(message=f"Using train data but no labels for unsupervised algorithm", print_message=output_configuration.verbose)
            data_train, _ = data_manager.load_raw_data(dataset_index, train=True)
        ground_truth_train = None

    # Read the test data
    __log(message=f">> Loading the test data", print_message=output_configuration.verbose)
    data_test, ground_truth_test = data_manager.load_raw_data(dataset_index, train=False)

    # Initialize the memory tracing variables to avoid warnings
    peak_memory_fitting = np.nan
    peak_memory_predicting = np.nan

    # Set the seed
    __log(message=f">> Setting the seed to '{seed}'", print_message=output_configuration.verbose)
    np.random.seed(seed=seed)
    results['Seed'] = seed

    try:
        # Fit the algorithm
        __log(message=f">> Fitting the algorithm", print_message=output_configuration.verbose)
        if output_configuration.trace_memory:
            tracemalloc.start()
        start_fitting = time.time()
        algorithm.fit(data_train, ground_truth_train)
        time_fitting = time.time() - start_fitting
        if output_configuration.trace_memory:
            _, peak_memory_fitting = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        # Predict the decision scores
        __log(message=f">> Predicting the decision scores on the test data",
              print_message=output_configuration.verbose)
        if output_configuration.trace_memory:
            tracemalloc.start()
        start_predicting = time.time()
        # decision_function instead of predict_proba to not include normalization time
        # Additionally, the scores are cached to avoid recomputing them.
        algorithm.decision_function(data_test)
        time_predicting = time.time() - start_predicting
        if output_configuration.trace_memory:
            _, peak_memory_predicting = tracemalloc.get_traced_memory()
            tracemalloc.stop()

    except Exception as e:
        message = f"An exception occurred while detecting anomalies!\n" \
                  f"Dataset index: {dataset_index}\n" \
                  f"Error message file: {output_configuration.error_log_file(dataset_index)}\n" \
                  "\n" \
                  f"Error message: {str(e)}"
        __log(message=message, print_message=output_configuration.verbose)
        if output_configuration.create_fit_predict_error_log:
            with open(output_configuration.error_log_file(dataset_index), 'w') as error_file:
                error_file.write(message)

        if output_configuration.reraise_fit_predict_errors:
            raise e

        return results

    # Write away the results
    __log(message=f">> Storing the results",
          print_message=output_configuration.verbose)
    __log(message=f"Computing the evaluation metrics metrics",
          print_message=output_configuration.verbose)
    predicted_proba = algorithm.predict_proba(data_test)

    for metric_name, metric in metrics.items():
        __log(message=f"Computing the evaluation metric '{metric_name}'",
              print_message=output_configuration.verbose)
        try:
            results[metric_name] = metric.compute(ground_truth_test, predicted_proba)
        except Exception:
            results[metric_name] = np.nan
        __log(message=f"Evaluation: '{results[metric_name]}'",
              print_message=output_configuration.verbose)
    if output_configuration.trace_time:
        __log(message=f"Saving the timing information",
              print_message=output_configuration.verbose)
        results['Time fit (s)'] = np.round(time_fitting, 5)
        results['Time predict (s)'] = np.round(time_predicting, 5)
    if output_configuration.trace_memory:
        __log(message=f"Saving the memory usage",
              print_message=output_configuration.verbose)
        results['Peak memory fit (KiB)'] = np.round(peak_memory_fitting / 1024, 5)
        results['Peak memory predict (KiB)'] = np.round(peak_memory_predicting / 1024, 5)

    # Save the anomaly scores plot, if requested
    if output_configuration.save_anomaly_scores_plot:
        __log(message=f">> Saving the anomaly score plot\n"
                      f"path: {output_configuration.anomaly_score_plot_path(dataset_index)}\n"
                      f"format: {output_configuration.anomaly_scores_plots_file_format}\n"
                      f"show_anomaly_scores: {output_configuration.anomaly_scores_plots_show_anomaly_scores}\n"
                      f"show_ground_truth: {output_configuration.anomaly_scores_plots_show_ground_truth}",
              print_message=output_configuration.verbose)
        fig = plot_anomaly_scores(
            trend_data=data_manager.load(dataset_index),
            anomaly_scores=algorithm.predict_proba(data_test),
            file_path=output_configuration.anomaly_score_plot_path(dataset_index),
            show_anomaly_scores=output_configuration.anomaly_scores_plots_show_anomaly_scores,
            show_ground_truth=output_configuration.anomaly_scores_plots_show_ground_truth
        )
        plt.close(fig)

    # Save the anomaly scores, if requested
    if output_configuration.save_anomaly_scores:
        __log(message=f">>> Saving the anomaly scores to disk\n"
                      f"path: {output_configuration.anomaly_scores_path(dataset_index)}",
              print_message=output_configuration.verbose)
        np.save(output_configuration.anomaly_scores_path(dataset_index), algorithm.decision_function(data_test))

    # Save the results after each iteration, if requested
    if output_configuration.save_results and output_configuration.constantly_save_results:
        __log(message=f">>> Saving the results to disk\n"
                      f"path: {output_configuration.results_path}",
              print_message=output_configuration.verbose)
        results.to_csv(output_configuration.intermediate_results_path(dataset_index))

    return results
