const { ethers } = require("hardhat");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deploying PredictionMarket with the account:", deployer.address);

    const PredictionMarket = await ethers.getContractFactory("PredictionMarket");
    const contract = await PredictionMarket.deploy();
    await contract.waitForDeployment();
    
    const address = await contract.getAddress();
    console.log("✅ PredictionMarket deployed to:", address);

    // 1. Create a test market
    console.log("\n1. Creating test market...");
    const claimId = "claim_tsmc_n2";
    const claimText = "台積電 2 奈米製程將於 2025 年開始量產";
    const stakeAmount = ethers.parseEther("0.01");

    const createTx = await contract.createMarket(claimId, claimText, { value: stakeAmount });
    await createTx.wait();
    console.log("Market created for:", claimId);

    // 2. Read back market data (ID starts at 1)
    console.log("\n2. Reading market status (ID: 1)...");
    let market = await contract.getMarket(1);
    console.log("Market Status:", market.status.toString(), "(Expected: 0 - PENDING)");

    // 3. Verify market
    console.log("\n3. Verifying market (ID: 1)...");
    const verifyTx = await contract.verifyMarket(1);
    await verifyTx.wait();
    console.log("Market verified.");

    // 4. Read back status again
    console.log("\n4. Confirming status change...");
    market = await contract.getMarket(1);
    console.log("Market Status:", market.status.toString(), "(Expected: 1 - VERIFIED)");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
