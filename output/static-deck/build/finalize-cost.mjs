import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const W='C:/Users/AKENA/Desktop/neonatal/output/static-deck',B=W+'/build',O=W+'/final';
const SK='C:/Users/AKENA/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations';
const candidate=B+'/candidate.pptx';
const {finalizePresentation}=await import(pathToFileURL(SK+'/container_tools/artifact_tool_utils.mjs').href);
console.log(await finalizePresentation({workspaceDir:W,candidatePath:candidate,finalPath:O+'/NeoGuard_Cost_Updated.pptx',pythonExecutable:'C:/Users/AKENA/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:SK+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:SK+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','13','--require-native-table-slide','15'],explicitTotalSlideCount:17,requiredNativeTableOwnerSlides:[13,15],fontPolicy:{basis:'design',families:['Arial','Arial Black','Georgia']},verifyArtifactToolImport:true,receiptPath:B+'/cost-validation.json'}));
