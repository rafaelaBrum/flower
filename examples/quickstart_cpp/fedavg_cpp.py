from ast import Bytes
from collections import OrderedDict
from io import BytesIO
import struct
from typing import Callable, Dict, List, Tuple

import numpy as np

from flwr.server.strategy import FedAvg
from flwr.common import (
    EvaluateRes,
    FitRes,
    Parameters,
    Scalar,
    Weights,
)
from typing import Optional
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate, weighted_loss_avg
from numpy import bytes_, numarray


class FedAvgCpp(FedAvg):
    def __init__(
        self,
        fraction_fit: float = 1.0,
        fraction_eval: float = 1.0,
        min_fit_clients: int = 2,
        min_eval_clients: int = 2,
        min_available_clients: int = 2,
        eval_fn: Optional[
            Callable[[Weights], Optional[Tuple[float, Dict[str, Scalar]]]]
        ] = None,
        on_fit_config_fn: Optional[Callable[[int], Dict[str, Scalar]]] = None,
        on_evaluate_config_fn: Optional[Callable[[int], Dict[str, Scalar]]] = None,
        accept_failures: bool = True,
        initial_parameters: Optional[Parameters] = None,
    ) -> None:
        super().__init__(
            fraction_fit=fraction_fit,
            fraction_eval=fraction_eval,
            min_fit_clients=min_fit_clients,
            min_eval_clients=min_eval_clients,
            min_available_clients=min_available_clients,
            eval_fn=eval_fn,
            on_fit_config_fn=on_fit_config_fn,
            on_evaluate_config_fn=on_evaluate_config_fn,
            accept_failures=accept_failures,
            initial_parameters=initial_parameters,
        )

    def aggregate_fit(
        self,
        rnd: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[BaseException],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """Aggregate fit results using weighted average."""
        if not results:
            return None, {}
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}
        # Convert results
        weights_results = [
            (parameters_to_weights(fit_res.parameters), fit_res.num_examples)
            for client, fit_res in results
        ]
        aggregated_weights = aggregate(weights_results)
        parameters_results = weights_to_parameters(aggregated_weights)

        return parameters_results, {}

    def aggregate_evaluate(
        self,
        rnd: int,
        results: List[Tuple[ClientProxy, EvaluateRes]],
        failures: List[BaseException],
    ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        """Aggregate evaluation losses using weighted average."""
        if not results:
            return None, {}
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}
        print(results[0][1])
        loss_aggregated = weighted_loss_avg(
            [
                (
                    evaluate_res.num_examples,
                    evaluate_res.loss,
                )
                for _, evaluate_res in results
            ]
        )
        return loss_aggregated, {}


def weights_to_parameters(weights) -> Parameters:
    tensors = [ndarray_to_bytes(tensor) for tensor in weights]
    return Parameters(tensors=tensors, tensor_type="cpp_double")


def parameters_to_weights(parameters: Parameters) -> Weights:
    """Convert parameters object to NumPy weights."""
    weights = [bytes_to_ndarray(tensor) for tensor in parameters.tensors]
    return weights


def bytes_to_ndarray(tensor_bytes: Bytes) -> np.ndarray:
    list_doubles = []
    for idx in range(0, len(tensor_bytes), 8):
        this_double = struct.unpack("d", tensor_bytes[idx : idx + 8])
        list_doubles.append(this_double[0])
    weights_np = np.asarray(list_doubles)
    return weights_np


def ndarray_to_bytes(a: np.ndarray) -> Bytes:
    doublelist = a.tolist()
    buf = struct.pack("%sd" % len(doublelist), *doublelist)
    return buf
