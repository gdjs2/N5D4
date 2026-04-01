# N5D4Disassembly, a neurosymbolic disassembly framework based on Logic Tensor Network.
# N5D4 is a disassembly (refinement) framework. It iteratively trains a neural model to
# predict whether each block is code or not, and redisassembles blocks predicted as code 
# to refine the disassembly result.
# 
# Requirements: ltntorch, networkx, torch installed in PyGhidra's Python environment.
# @author: Zhaoqi Xiao
# @category: Disassembly



import ltn
import networkx as nx
import torch
import torch.nn as nn

from datetime import datetime
from ltn import fuzzy_ops
from typing import Literal, Self

from ghidra.app.util import PseudoDisassembler, PseudoDisassemblerContext, PseudoInstruction  # pyright: ignore[reportMissingImports]
from ghidra.program.model.address import Address, AddressSet  # pyright: ignore[reportMissingImports]
from ghidra.program.model.listing import Instruction, Listing, Program, CommentType  # pyright: ignore[reportMissingImports]
from ghidra.program.model.mem import Memory  # pyright: ignore[reportMissingImports]
from ghidra.program.model.pcode import PcodeOp  # pyright: ignore[reportMissingImports]
from ghidra.program.model.scalar import Scalar  # pyright: ignore[reportMissingImports]
from ghidra.program.model.symbol import ReferenceManager  # pyright: ignore[reportMissingImports]

DEFAULT_ITERATION_LIMIT = 5
DEFAULT_EPOCH_LIMIT = 500

comparisonOpcodes = [
    PcodeOp.INT_EQUAL,
    PcodeOp.INT_NOTEQUAL,
    PcodeOp.INT_LESS,
    PcodeOp.INT_LESSEQUAL,
    PcodeOp.INT_SLESS,
    PcodeOp.INT_SLESSEQUAL,
]

arithmeticOpcodes = [
    PcodeOp.INT_ADD,
    PcodeOp.INT_SUB,
    PcodeOp.INT_MULT,
    PcodeOp.INT_DIV,
]

monitor = getMonitor()  # pyright: ignore[reportUndefinedVariable]

class Block:
    def __init__(
        self: Self,
        startAddress: Address,
        endAddress: Address,
        type: Literal["Code", "Data", "Unknown"],
        sectionName: str,
    ) -> None:
        self.startAddress: Address = startAddress
        self.endAddress: Address = endAddress
        self.type: Literal["Code", "Data", "Unknown"] = type
        self.sectionName: str = sectionName
        self.condBranchFlg: bool | None = None
        self.defUseFlg: bool | None = None
        self.veryShortFlg: bool | None = None
        self.highZeroRateFlg: bool | None = None
        self.highDefUseRateFlg: bool | None = None
        self.highContPrintableCharRateFlg: bool | None = None
        self.failedDisasmFlg: bool | None = None
        self.featureVector: list[float] | None = None
        self.pseudoInstrs: list[PseudoInstruction] | None = None

    def __repr__(self: Self) -> str:
        return (
            f"{self.type}Block:\n"
            f"  Address Range : [{self.startAddress} - {self.endAddress}] (l{self.startAddress.getOffset() // 4 + 1} - l{self.endAddress.getOffset() // 4 + 1})\n"
            f"  Section       : [{self.sectionName}]\n"
            f"  Flags:\n"
            f"    cond_branch        : {self.condBranchFlg}\n"
            f"    def_use            : {self.defUseFlg}\n"
            f"    very_short         : {self.veryShortFlg}\n"
            f"    high_zero_rate     : {self.highZeroRateFlg}\n"
            f"    high_def_use_rate  : {self.highDefUseRateFlg}\n"
            f"    high_printable_char: {self.highContPrintableCharRateFlg}\n"
            f"    failed_disasm      : {self.failedDisasmFlg}\n"
            f"  Feature Vector: {self.featureVector}"
        )

    def __str__(self: Self) -> str:
        return f"{self.type}Block @ [{self.startAddress} - {self.endAddress}]"

    @property
    def size(self: Self) -> int:
        return self.endAddress.subtract(self.startAddress) + 1


def extractAllBlocks(listing: Listing, memory: Memory) -> list[Block]:
    blocks: list[Block] = []

    monitor.initialize(len(memory.getBlocks()), "Extracting blocks from memory")

    for idx, memoryBlock in enumerate(memory.getBlocks()):
        monitor.setProgress(idx + 1)

        addr = memoryBlock.getStart()
        blockEndAddr = memoryBlock.getEnd().subtract(1)

        inCodeBlock = False
        codeStart = None
        inDataBlock = False
        dataStart = None
        inUnknownBlock = False
        unknownStart = None

        while addr <= blockEndAddr:
            codeUnit = listing.getCodeUnitAt(addr)

            if isinstance(codeUnit, Instruction):
                if inDataBlock:
                    blockEnd = codeUnit.getMinAddress().subtract(1)
                    blocks.append(Block(dataStart, blockEnd, "Data", memoryBlock.getName()))
                    inDataBlock = False
                    dataStart = None

                if inUnknownBlock:
                    blockEnd = codeUnit.getMinAddress().subtract(1)
                    blocks.append(Block(unknownStart, blockEnd, "Unknown", memoryBlock.getName()))
                    inUnknownBlock = False
                    unknownStart = None

                if not inCodeBlock:
                    codeStart = addr
                    inCodeBlock = True

                flowType = codeUnit.getFlowType()
                if flowType is not None and (
                    flowType.isCall() or flowType.isJump() or flowType.isTerminal()
                ):
                    blockEnd = codeUnit.getMaxAddress()
                    blocks.append(Block(codeStart, blockEnd, "Code", memoryBlock.getName()))
                    inCodeBlock = False
                    codeStart = None
            else:
                if codeUnit.getMnemonicString() == "??":
                    if inCodeBlock:
                        blockEnd = codeUnit.getMinAddress().subtract(1)
                        blocks.append(Block(codeStart, blockEnd, "Code", memoryBlock.getName()))
                        inCodeBlock = False
                        codeStart = None

                    if inDataBlock:
                        blockEnd = codeUnit.getMinAddress().subtract(1)
                        blocks.append(Block(dataStart, blockEnd, "Data", memoryBlock.getName()))
                        inDataBlock = False
                        dataStart = None

                    if not inUnknownBlock:
                        unknownStart = addr
                        inUnknownBlock = True
                else:
                    if inCodeBlock:
                        blockEnd = codeUnit.getMinAddress().subtract(1)
                        blocks.append(Block(codeStart, blockEnd, "Code", memoryBlock.getName()))
                        inCodeBlock = False
                        codeStart = None

                    if inUnknownBlock:
                        blockEnd = codeUnit.getMinAddress().subtract(1)
                        blocks.append(Block(unknownStart, blockEnd, "Unknown", memoryBlock.getName()))
                        inUnknownBlock = False
                        unknownStart = None

                    if not inDataBlock:
                        dataStart = addr
                        inDataBlock = True

            addr = addr.add(codeUnit.getLength())

        if inCodeBlock:
            blocks.append(Block(codeStart, blockEndAddr, "Code", memoryBlock.getName()))
        if inDataBlock:
            blocks.append(Block(dataStart, blockEndAddr, "Data", memoryBlock.getName()))
        if inUnknownBlock:
            blocks.append(Block(unknownStart, blockEndAddr, "Unknown", memoryBlock.getName()))

    return blocks


def pseudoDisassembleBlocks(blocks: list[Block], program: Program) -> None:
    pseudoDisassembler = PseudoDisassembler(program)

    monitor.initialize(len(blocks), "Pseudo disassembling blocks")

    for idx, block in enumerate(blocks):
        monitor.setProgress(idx + 1)
        ctx = PseudoDisassemblerContext(program.getProgramContext())
        ctx.flowStart(block.startAddress)

        instrs: list[PseudoInstruction] = []
        addr = block.startAddress
        while addr <= block.endAddress:
            instr = pseudoDisassembler.disassemble(addr, ctx, False)
            instrs.append(instr)
            if instr is not None:
                addr = instr.getMaxAddress().next()
            else:
                block.failedDisasmFlg = True
                addr = addr.add(4)

        if block.failedDisasmFlg is None:
            block.failedDisasmFlg = False
        block.pseudoInstrs = instrs


def splitDataBlocks(blocks: list[Block]) -> list[Block]:
    splitBlocks = []
    for block in blocks:
        if block.type == "Code" or block.pseudoInstrs is None:
            splitBlocks.append(block)
            continue

        lastInstrIdx = 0
        lastInstrAddress = block.startAddress
        for idx, instr in enumerate(block.pseudoInstrs):
            if instr is None:
                continue

            flowType = instr.getFlowType()
            if flowType is not None and (
                flowType.isCall() or flowType.isJump() or flowType.isTerminal()
            ):
                newBlock = Block(
                    lastInstrAddress,
                    instr.getMaxAddress(),
                    block.type,
                    block.sectionName,
                )
                newBlock.pseudoInstrs = block.pseudoInstrs[lastInstrIdx:idx + 1]
                newBlock.failedDisasmFlg = None in newBlock.pseudoInstrs
                splitBlocks.append(newBlock)
                lastInstrIdx = idx + 1
                lastInstrAddress = instr.getMaxAddress().add(1)

        if lastInstrIdx < len(block.pseudoInstrs):
            newBlock = Block(lastInstrAddress, block.endAddress, block.type, block.sectionName)
            newBlock.pseudoInstrs = block.pseudoInstrs[lastInstrIdx:]
            newBlock.failedDisasmFlg = None in newBlock.pseudoInstrs
            splitBlocks.append(newBlock)

    return splitBlocks


def getStringNumber(block: Block, refs: ReferenceManager, listing: Listing) -> int:
    stringNumber = 0
    if not block.pseudoInstrs:
        return stringNumber

    for instr in block.pseudoInstrs:
        if instr is None:
            continue

        references = refs.getReferencesFrom(instr.getAddress())
        for ref in references:
            data = listing.getDataAt(ref.getToAddress())
            if data and data.hasStringValue():
                stringNumber += 1
    return stringNumber


def getNumConstant(block: Block) -> int:
    constantCount = 0
    if not block.pseudoInstrs:
        return constantCount

    for instr in block.pseudoInstrs:
        if instr is None:
            continue

        for operandIdx in range(instr.getNumOperands()):
            for obj in instr.getOpObjects(operandIdx):
                if isinstance(obj, Scalar) or isinstance(obj, Address):
                    constantCount += 1
    return constantCount


def getTransferNumber(block: Block) -> int:
    transferCount = 0
    if not block.pseudoInstrs:
        return transferCount

    for instr in block.pseudoInstrs:
        if instr is None:
            continue
        if instr.getFlowType().isCall() or instr.getFlowType().isJump() or instr.getFlowType().isTerminal():
            transferCount += 1
    return transferCount


def getCallNumber(block: Block) -> int:
    callCount = 0
    if not block.pseudoInstrs:
        return callCount

    for instr in block.pseudoInstrs:
        if instr is None:
            continue
        if instr.getFlowType().isCall():
            callCount += 1
    return callCount


def getInstrNumber(block: Block) -> int:
    return sum(instr is not None for instr in block.pseudoInstrs) if block.pseudoInstrs else 0


def getArithmeticNumber(block: Block) -> int:
    arithmeticCount = 0
    if not block.pseudoInstrs:
        return arithmeticCount

    for instr in block.pseudoInstrs:
        if instr is None:
            continue
        for op in instr.getPcode():
            if op.getOpcode() in arithmeticOpcodes:
                arithmeticCount += 1
    return arithmeticCount


def getZeroBytesNumber(block: Block, memory: Memory) -> int:
    zeroBytesCount = 0
    addr = block.startAddress
    while addr <= block.endAddress:
        try:
            data = memory.getByte(addr) & 0xFF
            if data == 0:
                zeroBytesCount += 1
        except Exception:
            pass
        addr = addr.add(1)

    block.highZeroRateFlg = zeroBytesCount * 2 >= block.endAddress.subtract(block.startAddress)
    return zeroBytesCount


def getDefUseNumber(block: Block) -> int:
    defUseCount = 0
    definitions = {}
    if block.pseudoInstrs is None:
        block.highDefUseRateFlg = False
        return defUseCount

    for instrIdx, instr in enumerate(block.pseudoInstrs):
        expiredDefs = [definition for definition, index in definitions.items() if index - instrIdx > 16]
        for definition in expiredDefs:
            del definitions[definition]

        if instr is None:
            continue

        instrDefinitions = {}
        for op in instr.getPcode():
            for use in op.getInputs():
                if use in definitions:
                    defUseCount += 1
            instrDefinitions[op.getOutput()] = instrIdx
        definitions.update(instrDefinitions)

    block.highDefUseRateFlg = defUseCount * 3 >= block.endAddress.subtract(block.startAddress)
    return defUseCount


def getPrintableCharNumber(block: Block, memory: Memory) -> int:
    printableCount = 0
    continuousPrintableCount = 0
    maxContinuousPrintableCount = 0
    addr = block.startAddress

    while addr <= block.endAddress:
        try:
            data = memory.getByte(addr) & 0xFF
            if 32 <= data <= 126:
                printableCount += 1
                continuousPrintableCount += 1
                if continuousPrintableCount > maxContinuousPrintableCount:
                    maxContinuousPrintableCount = continuousPrintableCount
            else:
                continuousPrintableCount = 0
        except Exception:
            pass
        addr = addr.add(1)

    block.highContPrintableCharRateFlg = (
        maxContinuousPrintableCount * 2 >= block.endAddress.subtract(block.startAddress)
    )
    return printableCount


def getFeatureVector(
    blocks: list[Block],
    refs: ReferenceManager,
    listing: Listing,
    memory: Memory,
) -> None:
    
    monitor.initialize(len(blocks), "Calculating feature vectors for blocks")
    for idx, block in enumerate(blocks):
        monitor.setProgress(idx + 1)
        blockSize = block.endAddress.subtract(block.startAddress) + 1
        block.featureVector = [
            getStringNumber(block, refs, listing) / blockSize,
            getNumConstant(block) / blockSize,
            getTransferNumber(block) / blockSize,
            getCallNumber(block) / blockSize,
            getInstrNumber(block) / blockSize,
            getArithmeticNumber(block) / blockSize,
            getZeroBytesNumber(block, memory) / blockSize,
            getDefUseNumber(block) / blockSize,
            getPrintableCharNumber(block, memory) / blockSize,
        ]


def checkCompareBranch(blocks: list[Block], program: Program) -> None:
    del program
    for block in blocks:
        if block.pseudoInstrs is None:
            block.condBranchFlg = None
            continue

        reversedInstrs = block.pseudoInstrs[::-1]
        firstInstr = reversedInstrs[0]
        if firstInstr is None:
            block.condBranchFlg = None
        elif firstInstr.getFlowType().isConditional():
            detectCompFlg = False
            for instr in reversedInstrs[1:]:
                if instr is None:
                    continue
                if any(op.getOpcode() in comparisonOpcodes for op in instr.getPcode()):
                    detectCompFlg = True
                    break
            block.condBranchFlg = detectCompFlg


def generateEmbeddingsFromFeatureVector(blocks: list[Block]) -> torch.Tensor:
    embeddings = []
    for block in blocks:
        embeddings.append(torch.tensor(block.featureVector, dtype=torch.float32))
    return torch.stack(embeddings, dim=0)


def createGraph(program: Program):
    listing = program.getListing()
    memory = program.getMemory()

    blocks = extractAllBlocks(listing, memory)
    blocks.sort(key=lambda block: block.startAddress)

    pseudoDisassembleBlocks(blocks, program)
    blocks = splitDataBlocks(blocks)

    fallThroughEdges = _getFallthroughEdges(blocks)
    callEdges = _getCallEdges(blocks, listing)

    graph = nx.DiGraph()
    graph.add_nodes_from(blocks)
    graph.add_edges_from(fallThroughEdges, type="fallthrough")
    graph.add_edges_from(callEdges, type="call")
    return graph


def _bisearchAddrInBlocks(blocks: list[Block], addr: Address) -> Block | None:
    left, right = 0, len(blocks)
    while left < right:
        mid = (left + right) >> 1
        if blocks[mid].startAddress <= addr <= blocks[mid].endAddress:
            return blocks[mid]
        if addr < blocks[mid].startAddress:
            right = mid
        else:
            left = mid + 1
    return None


def _getCallEdges(blocks: list[Block], listing: Listing) -> list[tuple[Block, Block]]:
    callEdges = []
    blocks.sort(key=lambda block: block.startAddress)

    for block in blocks:
        if block.type != "Code":
            continue
        addrSet = AddressSet(block.startAddress, block.endAddress)
        instructions = listing.getInstructions(addrSet, True)
        for instr in instructions:
            for ref in instr.getReferencesFrom():
                if ref.getReferenceType().isFlow():
                    targetBlock = _bisearchAddrInBlocks(blocks, ref.getToAddress())
                    if targetBlock is not None:
                        callEdges.append((block, targetBlock))
    return callEdges


def _getFallthroughEdges(blocks: list[Block]) -> list[tuple[Block, Block]]:
    fallThroughEdges = []
    blocks.sort(key=lambda block: block.startAddress)

    for index in range(len(blocks) - 1):
        currentBlock = blocks[index]
        if currentBlock.pseudoInstrs is None:
            continue

        lastInstr = currentBlock.pseudoInstrs[-1]
        if lastInstr is None:
            continue

        if lastInstr.hasFallthrough():
            fallThroughEdges.append((currentBlock, blocks[index + 1]))
    return fallThroughEdges


class MLPClassifier(nn.Module):
    def __init__(self, inputDim=32, hiddenDim1=64, hiddenDim2=32):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(inputDim, hiddenDim1),
            nn.ReLU(),
            nn.Linear(hiddenDim1, hiddenDim2),
            nn.ReLU(),
            nn.Linear(hiddenDim2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.classifier(x).squeeze(-1)


class MyProgram:
    def __init__(self, program: Program):
        listing = program.getListing()
        memory = program.getMemory()
        refManager = program.getReferenceManager()

        self.graph = createGraph(program)
        self.blocks: list[Block] = list(self.graph.nodes)
        self.blocks.sort(key=lambda block: block.startAddress)

        getFeatureVector(self.blocks, refManager, listing, memory)
        checkCompareBranch(self.blocks, program)

        self.embeddings = generateEmbeddingsFromFeatureVector(self.blocks)
        self.block2idx = {block: idx for idx, block in enumerate(self.blocks)}

    def getRelVars(self: Self, edgeType: str) -> tuple[ltn.Variable, ltn.Variable] | tuple[None, None]:
        edgesIdx = torch.tensor(
            [
                (self.block2idx[u], self.block2idx[v])
                for u, v in self.graph.edges()
                if self.graph[u][v]["type"] == edgeType
            ],
            dtype=torch.long,
        )
        if edgesIdx.numel() == 0:
            return (None, None)

        leftEmbeddings = self.embeddings[edgesIdx[:, 0]]
        rightEmbeddings = self.embeddings[edgesIdx[:, 1]]
        return (
            ltn.Variable(f"{edgeType}_rel_left", leftEmbeddings),
            ltn.Variable(f"{edgeType}_rel_right", rightEmbeddings),
        )

    def getIdentityVars(self: Self, field: str, val: Literal["Code", "Data"] | bool) -> ltn.Variable | None:
        matchedBlocksIdx = torch.tensor(
            [self.block2idx[block] for block in self.blocks if getattr(block, field) == val],
            dtype=torch.long,
        )
        if matchedBlocksIdx.numel() == 0:
            return None
        return ltn.Variable(f"{field}_{val}_id", self.embeddings[matchedBlocksIdx])


def train(
    myProgram: MyProgram,
    codeBlock: ltn.Predicate | None = None,
    epochs: int = 1000,
) -> tuple[ltn.Predicate, float]:
    if not codeBlock:
        codeBlock = ltn.Predicate(
            MLPClassifier(
                inputDim=myProgram.embeddings.size(1),
                hiddenDim1=32,
                hiddenDim2=64,
            ).to(ltn.device)
        )

    satAgg = fuzzy_ops.SatAgg(fuzzy_ops.AggregPMeanError(p=4))
    forall = ltn.Quantifier(fuzzy_ops.AggregPMeanError(p=4), quantifier="f")
    equiv = ltn.Connective(fuzzy_ops.Equiv(fuzzy_ops.AndProd(), fuzzy_ops.ImpliesReichenbach()))
    implies = ltn.Connective(fuzzy_ops.ImpliesReichenbach())
    notOp = ltn.Connective(fuzzy_ops.NotStandard())

    xCall, yCall = myProgram.getRelVars("call")
    xFt, yFt = myProgram.getRelVars("fallthrough")

    condBrchT = myProgram.getIdentityVars("condBranchFlg", True)
    condBrchF = myProgram.getIdentityVars("condBranchFlg", False)
    highZeroRate = myProgram.getIdentityVars("highZeroRateFlg", True)
    highContPrintableCharRate = myProgram.getIdentityVars("highContPrintableCharRateFlg", True)
    failedDisasm = myProgram.getIdentityVars("failedDisasmFlg", True)
    disasmGtCb = myProgram.getIdentityVars("type", "Code")
    disasmGtDb = myProgram.getIdentityVars("type", "Data")

    optimizer = torch.optim.Adam(list(codeBlock.parameters()), lr=0.001)
    start = datetime.now()

    monitor.initialize(epochs, "Training MLP Classifier for CodeBlock Predicate")

    for epoch in range(epochs):
        if xFt and yFt:
            ltn.diag(xFt, yFt)
        if xCall and yCall:
            ltn.diag(xCall, yCall)

        optimizer.zero_grad()
        satAggList = []

        if disasmGtCb:
            satAggList.append(forall([disasmGtCb], codeBlock(disasmGtCb)))
        if disasmGtDb:
            satAggList.append(forall([disasmGtDb], notOp(codeBlock(disasmGtDb))))

        if condBrchT:
            satAggList.append(forall([condBrchT], codeBlock(condBrchT)))
        if condBrchF:
            satAggList.append(forall([condBrchF], notOp(codeBlock(condBrchF))))
        if highZeroRate:
            satAggList.append(forall([highZeroRate], notOp(codeBlock(highZeroRate))))
        if xFt and yFt:
            satAggList.append(forall([xFt, yFt], implies(codeBlock(xFt), codeBlock(yFt))))
        if xCall and yCall:
            satAggList.append(forall([xCall, yCall], equiv(codeBlock(xCall), codeBlock(yCall))))
        if highContPrintableCharRate:
            satAggList.append(
                forall([highContPrintableCharRate], notOp(codeBlock(highContPrintableCharRate)))
            )
        if failedDisasm:
            satAggList.append(forall([failedDisasm], notOp(codeBlock(failedDisasm))))

        satAggScore = satAgg(*satAggList)
        loss = 1.0 - satAggScore
        loss.backward()
        optimizer.step()

        monitor.setProgress(epoch+1)
        if epoch % 100 == 0:
            print(f"Epoch {epoch}, Loss: {loss.item():.5f}")
        if loss.item() < 0.01:
            print(f"Early stopping at epoch {epoch}, Loss: {loss.item():.5f}")
            break

    print(
        f"Training completed in {(datetime.now() - start).total_seconds():.2f}s, final loss: {loss.item():.5f}"
    )
    return (codeBlock, loss.item())


def redisassemble(codeBlock: ltn.Predicate, myProgram: MyProgram, listing: Listing) -> int:
    cnt = 0
    for block, emb in zip(myProgram.blocks, myProgram.embeddings):
        if (confidence := codeBlock(ltn.Constant(emb)).value) >= 0.50 and block.type != "Code" and not block.failedDisasmFlg:
            clearListing(block.startAddress, block.endAddress)  # pyright: ignore[reportUndefinedVariable]
            if disassemble(block.startAddress):  # pyright: ignore[reportUndefinedVariable]
                listing.setComment(block.startAddress, CommentType.PRE, f"N5D4 Redisassembled Code Block (confidence: {confidence:.2f})")  # pyright: ignore[reportUndefinedVariable]
                cnt += 1

    return cnt


def run(currentProgram: Program, iterationLimitArg: int = DEFAULT_ITERATION_LIMIT, epochLimitArg: int = DEFAULT_EPOCH_LIMIT) -> None:

    if currentProgram is None:
        print("No program loaded. Please load a program and try again.")
        return

    print(
        f"""
=========== N5D4 Disassembly Script ===========
Program: {currentProgram.getName()}
Device: {ltn.device}
"""
    )

    finishFlag = False
    iterationCount = 0
    codeBlock = None

    while not finishFlag and iterationCount < iterationLimitArg:
        iterationCount += 1
        myProgram = MyProgram(currentProgram)
        codeBlock, _ = train(myProgram, codeBlock, epochLimitArg)
        redisassembleCount = redisassemble(codeBlock, myProgram, currentProgram.getListing())

        if redisassembleCount == 0:
            finishFlag = True
            print(f"Iteration {iterationCount}: No blocks to redisassemble, finishing.")
        else:
            print(f"Iteration {iterationCount}: Redisassembled {redisassembleCount} blocks.")

def askParameters() -> tuple[int, int]:
    iterationLimit = DEFAULT_ITERATION_LIMIT
    epochLimit = DEFAULT_EPOCH_LIMIT
    
    iterationLimit = askInt("Iteration Limit", "Enter the maximum number of iterations:")  # pyright: ignore[reportUndefinedVariable]
    epochLimit = askInt("Epoch Limit", "Enter the maximum number of epochs for training:")  # pyright: ignore[reportUndefinedVariable]

    return iterationLimit, epochLimit


def main() -> None:
    iterationLimit, epochLimit = askParameters()
    currentProgram = getCurrentProgram()  # pyright: ignore[reportUndefinedVariable]
    run(currentProgram, iterationLimit, epochLimit)
    analyzeAll(currentProgram)  # pyright: ignore[reportUndefinedVariable]


__all__ = [
    "arithmeticOpcodes",
    "Block",
    "comparisonOpcodes",
    "MLPClassifier",
    "MyProgram",
    "checkCompareBranch",
    "createGraph",
    "extractAllBlocks",
    "generateEmbeddingsFromFeatureVector",
    "getArithmeticNumber",
    "getCallNumber",
    "getDefUseNumber",
    "getFeatureVector",
    "getInstrNumber",
    "getNumConstant",
    "getPrintableCharNumber",
    "getStringNumber",
    "getTransferNumber",
    "getZeroBytesNumber",
    "main",
    "pseudoDisassembleBlocks",
    "redisassemble",
    "run",
    "splitDataBlocks",
    "train",
]


if __name__ == "__main__":
    main()