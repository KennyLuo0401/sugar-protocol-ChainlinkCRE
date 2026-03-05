const { ethers } = require("hardhat");

async function main() {
    console.log("🍬 Deploying ResolutionRecord to Tenderly Virtual TestNet...\n");

    const [deployer] = await ethers.getSigners();
    console.log("Deployer address:", deployer.address);

    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "ETH\n");

    // Deploy
    const ResolutionRecord = await ethers.getContractFactory("ResolutionRecord");
    const contract = await ResolutionRecord.deploy();
    await contract.waitForDeployment();

    const address = await contract.getAddress();
    console.log("✅ ResolutionRecord deployed to:", address);
    console.log("\n📝 Save this address! You need it for CRE workflow config.");

    // 寫一筆測試交易，讓 Tenderly Explorer 有紀錄
    console.log("\n📤 Recording a test resolution...");
    const tx = await contract.recordResolution(
        "claim_tsmc_n2",
        true,
        "台積電 2 奈米製程確認將於 2025 年量產，經 Chainlink CRE 驗證為 TRUE。"
    );
    await tx.wait();
    console.log("✅ Test resolution recorded! TX hash:", tx.hash);

    // 讀取驗證
    const resolution = await contract.getResolution("claim_tsmc_n2");
    console.log("\n📖 Verification read:");
    console.log("  verdict:", resolution.verdict);
    console.log("  reasoning:", resolution.reasoning);
    console.log("  timestamp:", resolution.timestamp.toString());

    console.log("\n🎉 Done! Check your Tenderly Dashboard for the transactions.");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
