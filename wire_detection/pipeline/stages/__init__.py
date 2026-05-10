from wire_detection.pipeline.stages.crop import CropStage
from wire_detection.pipeline.stages.mask import MaskStage
from wire_detection.pipeline.stages.threshold import ThresholdStage
from wire_detection.pipeline.stages.invert import InvertStage
from wire_detection.pipeline.stages.dilate import DilateStage
from wire_detection.pipeline.stages.ccl import CCLStage
from wire_detection.pipeline.stages.contour_extract import ContourExtractStage
from wire_detection.pipeline.stages.dedup import DedupStage
from wire_detection.pipeline.stages.length_filter import LengthFilterStage
from wire_detection.pipeline.registry import register_stage

register_stage("crop", CropStage)
register_stage("mask", MaskStage)
register_stage("threshold", ThresholdStage)
register_stage("invert", InvertStage)
register_stage("dilate", DilateStage)
register_stage("ccl", CCLStage)
register_stage("contour_extract", ContourExtractStage)
register_stage("dedup", DedupStage)
register_stage("length_filter", LengthFilterStage)
