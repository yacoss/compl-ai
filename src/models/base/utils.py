#    Copyright 2024 SRI Lab @ ETH Zurich, LatticeFlow AI, INSAIT
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import gc
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar, Union

import torch
import transformers

# LM Harness Utils
T = TypeVar("T")


def _get_dtype(
    dtype: Union[str, torch.dtype], config: Optional[transformers.AutoConfig] = None
) -> torch.dtype:
    """Converts `dtype` from `str` to torch.dtype when possible. @LLM Harness"""
    if dtype is None and config is not None:
        _torch_dtype = config.torch_dtype
    elif isinstance(dtype, str) and dtype != "auto":
        # Convert `str` args torch dtype: `float16` -> `torch.float16`
        _torch_dtype = getattr(torch, dtype)
    else:
        _torch_dtype = dtype
    return _torch_dtype


def clear_torch_cache():
    gc.collect()
    torch.cuda.empty_cache()


def chunks(iter: Iterable[T], n=0, fn: Optional[Callable[[int], int]] = None) -> Iterable[List[T]]:
    """
    Splits an iterable into chunks of size `n` or `fn(i)`.
    """

    arr = []
    for i, x in enumerate(iter):
        arr.append(x)
        if len(arr) == (fn(i) if fn else n):
            yield arr
            arr = []

    if arr:
        yield arr


def make_disjoint_window(pair: Tuple[List[int], List[int]]) -> Tuple[List[int], List[int]]:
    """Splits a window from get_rolling_token_windows into disjoint input and prediction windows.
        Example:    input_tokens: 0 1 2 3 4 5 6 7 8
                     pred_tokens:       3 4 5 6 7 8
        becomes:
                    input_tokens: 0 1 2
                     pred_tokens:       3 4 5 6 7 8
    Args:
        pair (Tuple[List[int], List[int]]): Window from get_rolling_token_windows

    Returns:
        Tuple[List[int], List[int]]: Corresponding input and prediction windows
    """
    input_tokens, pred_tokens = pair

    return input_tokens[: len(input_tokens) - len(pred_tokens) + 1], pred_tokens


def get_rolling_token_windows(
    token_list: List[int], prefix_token: int, max_seq_len: int, context_len: int
) -> Iterable[Tuple[List[int], List[int]]]:
    """Generates rolling windows of tokens from a list of tokens.
    Given input tokens 0 1 2 3 4 5 6 7 8 and prefix token P and max_seq_len 3 context_len 2,
    the following windows are generated:
                0 1 2 3 4 5 6 7 8
    window 1: P 0 1                 <- Context
                0 1 2               <- Prediction
    window 2:     1 2 3
                      3 4
    window 3:         3 4 5
                          5 6
    window 4:             5 6 7
                              7 8

    Essentially the minimal context for each prediction is context_len (with exception of the first window).
    Note that in case we have max_seq_len == context_len, we predict most of the tokens individually with full sized contexts.

    Args:
        token_list (List[int]): List of tokens to split into windows
        prefix_token (int): Initiaé token to use for the first window
        max_seq_len (int): Max length of a sequence
        context_len (int): SIze of the context window

    Returns:
        Iterable[Tuple[List[int], List[int]]]: The respective windows of tokens

    Yields:
        Iterator[Iterable[Tuple[List[int], List[int]]]]: See above
    """

    assert 1 <= context_len <= max_seq_len
    if not token_list:
        return
    # +1 offset, going from input->preds
    pred_len = max_seq_len - context_len + 1
    predicted = 0

    # Special handling for first window: predict all tokens
    first_seq_len = min(max_seq_len, len(token_list))
    yield ([prefix_token] + token_list[: first_seq_len - 1], token_list[:first_seq_len])
    predicted += first_seq_len  # 3

    while predicted < len(token_list):
        window_pred_len = min(len(token_list) - predicted, pred_len)
        window_end = predicted + window_pred_len

        yield (
            token_list[window_end - max_seq_len - 1 : window_end - 1],
            token_list[window_end - window_pred_len : window_end],
        )
        predicted += window_pred_len


def select_continuation_from_batch_left_padding(
    generations: Union[List[List[int]], torch.Tensor], max_context_size: int
):
    """Select the continuation from the batch, removing prompts of different lengths.
    Args:
        generations (Union[List[List[int]], torch.Tensor]):
            A tensor or list-of-lists of shape [batch_size, sequence length].
        max_context_size (int):
            The size of the biggest context; generations will proceed from that
            index.
    Example:
        PAD     PAD Continue : The dog chased the cat [every      day of  the week]
        Riddle  me    this   : The dog chased the cat [yesterday] PAD PAD PAD PAD
    Output:
        [every       day of  the week]
        [yesterday]  PAD PAD PAD PAD
    """
    if isinstance(generations, List):
        return [gen[max_context_size:] for gen in generations]
    return generations[:, max_context_size:]
