from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class SimpleHelloCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{register capability}}

    async def run(self):
        try:
            await self.capability_worker.speak(
                "こんにちは。OpenHome の簡易 Ability が正しく動作しています。"
            )
        except Exception as error:
            self.worker.editor_logging_handler.error(
                f"SimpleHelloCapability failed: {error}"
            )
            await self.capability_worker.speak(
                "簡易 Ability の実行中にエラーが発生しました。"
            )
        finally:
            self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.run())
